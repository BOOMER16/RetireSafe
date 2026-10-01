"""Build the pilot scenario with real tools against a local AWS emulator.

Runs Terraform (real binary, real hashicorp/aws provider) against a moto server,
then captures genuine tool output into pilot/generated/:

  plan_before.json      terraform show -json of the proposed deletion (app v1 -> v2)
  route53_before.json   Route 53 list-resource-record-sets (boto3) while DNS v1 is live
  zone_before.db        the same records as a BIND zone file (dnspython)
  route53_after.json    after the DNS team removes the two references (DNS v2)
  plan_after.json       terraform show -json after applying the tombstone patch (app v1 -> v3)
  manifest.json         tool versions and SHA-256 of every output

Usage: python pilot/scripts/build_scenario.py [--terraform PATH] [--tf-config PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import boto3
import dns.rdata
import dns.rdataclass
import dns.rdatatype
import dns.zone

PILOT = Path(__file__).resolve().parents[1]
TF_SRC = PILOT / "terraform"
WORK = PILOT / ".work"
OUT = PILOT / "generated"
PORT = 5055
ENDPOINT = f"http://127.0.0.1:{PORT}"


def sh(cmd: list[str], cwd: Path, env: dict) -> str:
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed in {cwd}: {' '.join(cmd)}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r.stdout


def wait_port(port: int, timeout: float = 30) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.3)
    sys.exit("moto server did not start")


def stage(root: str, variant: str) -> Path:
    d = WORK / root
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(TF_SRC / "providers.tf.tmpl", d / "providers.tf")
    shutil.copy(TF_SRC / root / f"{variant}.tf", d / "main.tf")
    return d


def export_route53(name: str) -> list[dict]:
    r53 = boto3.client("route53", endpoint_url=ENDPOINT, region_name="us-east-1",
                       aws_access_key_id="pilot", aws_secret_access_key="pilot")
    zone = next(z for z in r53.list_hosted_zones()["HostedZones"] if z["Name"] == "retiresafe-pilot.example.")
    sets = r53.list_resource_record_sets(HostedZoneId=zone["Id"])["ResourceRecordSets"]
    (OUT / name).write_text(json.dumps({"ResourceRecordSets": sets}, indent=2) + "\n", encoding="utf-8")
    return sets


def bind_zone(sets: list[dict], name: str) -> None:
    z = dns.zone.Zone("retiresafe-pilot.example.", relativize=False)
    for rs in sets:
        node = z.find_node(rs["Name"], create=True)
        rdtype = dns.rdatatype.from_text(rs["Type"])
        rds = node.find_rdataset(dns.rdataclass.IN, rdtype, create=True)
        rds.update_ttl(rs.get("TTL", 300))
        for v in rs.get("ResourceRecords", []):
            val = v["Value"]
            m = re.fullmatch(r"\{'Value': '(.*)'\}", val)   # moto quirk: SOA value returned as a dict repr
            if m:
                val = m.group(1)
            if rs["Type"] in ("CNAME", "NS") and not val.endswith("."):
                val += "."
            rds.add(dns.rdata.from_text(dns.rdataclass.IN, rdtype, val))
    (OUT / name).write_text(z.to_text(relativize=False) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--terraform", default=shutil.which("terraform") or "/home/user/tools/terraform")
    ap.add_argument("--tf-config", default=os.environ.get("TF_CLI_CONFIG_FILE", "/home/user/tools/terraformrc"))
    a = ap.parse_args()
    try:
        socket.gethostbyname("123456789012.s3control.pilot.internal")
    except OSError:
        sys.exit("add this loopback entry first (S3 Control prefixes the account id to the host):\n"
                 "  echo '127.0.0.1 s3control.pilot.internal 123456789012.s3control.pilot.internal' "
                 ">> /etc/hosts")
    shutil.rmtree(WORK, ignore_errors=True)
    OUT.mkdir(exist_ok=True)
    env = {**os.environ, "TF_CLI_CONFIG_FILE": a.tf_config, "TF_IN_AUTOMATION": "1",
           "AWS_EC2_METADATA_DISABLED": "true", "CHECKPOINT_DISABLE": "1"}
    tf = a.terraform
    moto = subprocess.Popen([sys.executable, "-m", "moto.server", "-H", "127.0.0.1", "-p", str(PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_port(PORT)
        flags = ["-input=false", "-no-color"]
        d = stage("dns", "v1")
        sh([tf, "init", *flags], d, env)
        sh([tf, "apply", "-auto-approve", *flags], d, env)
        bind_zone(export_route53("route53_before.json"), "zone_before.db")

        a_dir = stage("app", "v1")
        sh([tf, "init", *flags], a_dir, env)
        sh([tf, "apply", "-auto-approve", *flags], a_dir, env)
        stage("app", "v2")
        sh([tf, "plan", "-out=before.tfplan", *flags], a_dir, env)
        (OUT / "plan_before.json").write_text(sh([tf, "show", "-json", "before.tfplan"], a_dir, env), encoding="utf-8")

        stage("dns", "v2")
        sh([tf, "apply", "-auto-approve", *flags], d, env)
        export_route53("route53_after.json")

        stage("app", "v3")
        sh([tf, "plan", "-out=after.tfplan", *flags], a_dir, env)
        (OUT / "plan_after.json").write_text(sh([tf, "show", "-json", "after.tfplan"], a_dir, env), encoding="utf-8")

        version = json.loads(sh([tf, "version", "-json"], a_dir, env))
        import moto as moto_pkg
        manifest = {
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "terraform": version.get("terraform_version"),
            "providers": version.get("provider_selections"),
            "moto": moto_pkg.__version__, "boto3": boto3.__version__,
            "note": "Real Terraform and AWS provider output against a moto emulator. Resource names and the "
                    "retiresafe-pilot.example zone are an invented scenario (.example is reserved, RFC 2606). "
                    "Known emulator quirk: moto returns the SOA value as a Python dict repr; RetireSafe does not "
                    "use SOA records.",
            "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(OUT.iterdir()) if p.name != "manifest.json"},
        }
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(manifest, indent=2))
    finally:
        moto.terminate()
        moto.wait(timeout=10)


if __name__ == "__main__":
    main()
