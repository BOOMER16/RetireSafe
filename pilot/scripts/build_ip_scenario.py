"""Build the IP-address scenario with real Terraform + AWS provider against moto (EC2 + Route 53).

v1  creates an instance with a public IP, an Elastic IP, and A records pointing at both.
v2  deletes the instance and the Elastic IP but keeps the A records  -> generated/ip_plan_before.json
v3  deletes the instance, the Elastic IP and the A records together  -> generated/ip_plan_after.json
The Route 53 export taken while v1 is live is generated/ip_route53.json.

Usage: python pilot/scripts/build_ip_scenario.py   (same prerequisites as build_scenario.py)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_scenario as bs  # noqa: E402

V3 = '''resource "aws_route53_zone" "ipzone" {
  name = "ip.retiresafe-pilot.example"
}
'''


def main() -> None:
    tf = shutil.which("terraform") or "/home/user/tools/terraform"
    env = {**os.environ, "TF_CLI_CONFIG_FILE": os.environ.get("TF_CLI_CONFIG_FILE", "/home/user/tools/terraformrc"),
           "TF_IN_AUTOMATION": "1", "AWS_EC2_METADATA_DISABLED": "true", "CHECKPOINT_DISABLE": "1"}
    work = bs.WORK / "ip"
    shutil.rmtree(work, ignore_errors=True)
    bs.OUT.mkdir(exist_ok=True)
    moto = subprocess.Popen([sys.executable, "-m", "moto.server", "-H", "127.0.0.1", "-p", str(bs.PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    flags = ["-input=false", "-no-color"]
    try:
        bs.wait_port(bs.PORT)
        d = bs.stage("ip", "v1")
        bs.sh([tf, "init", *flags], d, env)
        bs.sh([tf, "apply", "-auto-approve", *flags], d, env)
        state = json.loads(bs.sh([tf, "show", "-json"], d, env))
        res = {r["address"]: r["values"] for r in state["values"]["root_module"]["resources"]}
        eip, web = res["aws_eip.api"]["public_ip"], res["aws_instance.web"]["public_ip"]
        sets = bs.export_route53("ip_route53.json") if False else None
        import boto3
        r53 = boto3.client("route53", endpoint_url=bs.ENDPOINT, region_name="us-east-1",
                           aws_access_key_id="pilot", aws_secret_access_key="pilot")
        zone = next(z for z in r53.list_hosted_zones()["HostedZones"] if z["Name"] == "ip.retiresafe-pilot.example.")
        sets = r53.list_resource_record_sets(HostedZoneId=zone["Id"])["ResourceRecordSets"]
        (bs.OUT / "ip_route53.json").write_text(json.dumps({"ResourceRecordSets": sets}, indent=2) + "\n",
                                                encoding="utf-8")
        v2 = (bs.TF_SRC / "ip" / "v2.tf").read_text(encoding="utf-8").replace("PLACEHOLDER_EIP", eip) \
            .replace("PLACEHOLDER_WEB", web)
        (d / "main.tf").write_text(v2, encoding="utf-8")
        bs.sh([tf, "plan", "-out=before.tfplan", *flags], d, env)
        (bs.OUT / "ip_plan_before.json").write_text(bs.sh([tf, "show", "-json", "before.tfplan"], d, env),
                                                    encoding="utf-8")
        (d / "main.tf").write_text(V3, encoding="utf-8")
        bs.sh([tf, "plan", "-out=after.tfplan", *flags], d, env)
        (bs.OUT / "ip_plan_after.json").write_text(bs.sh([tf, "show", "-json", "after.tfplan"], d, env),
                                                   encoding="utf-8")
        man = json.loads((bs.OUT / "manifest.json").read_text(encoding="utf-8"))
        for n in ("ip_route53.json", "ip_plan_before.json", "ip_plan_after.json"):
            man["files"][n] = hashlib.sha256((bs.OUT / n).read_bytes()).hexdigest()
        man["ip_scenario"] = {"elastic_ip": eip, "instance_public_ip": web,
                              "note": "IPs are allocated by the moto emulator, not by AWS"}
        (bs.OUT / "manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(man["ip_scenario"], indent=2))
    finally:
        moto.terminate()
        moto.wait(timeout=10)


if __name__ == "__main__":
    main()
