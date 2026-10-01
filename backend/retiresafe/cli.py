"""Command-line interface.

    retiresafe assess --plan plan.json [--dns zone.json] [--repo app=./app] \
        [--log access.log,format=clf,host=www.example.com] [--policy policy.json] \
        --out evidence.json [--markdown report.md]
    retiresafe scan --hosts hosts.txt | --dns zone.json  [--out findings.json]
    retiresafe serve [--host 127.0.0.1] [--port 8080]
    retiresafe sources

Exit codes: 0 gate passed / no reclaimable drift, 2 gate failed, 3 reclaimable drift found, 1 usage or input error.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .collectors import dns_zone
from .config import log_from, parse_as_of, policy_dict, policy_from
from .engine.assess import AssessmentInput, run
from .knowledge.sources import SOURCES
from .report import evidence


def _kv(spec: str) -> tuple[str, dict]:
    path, *opts = spec.split(",")
    d: dict = {}
    for o in opts:
        k, _, v = o.partition("=")
        d[k.strip()] = v.strip().split("|") if k.strip() == "covers" else v.strip()
    return path, d


def cmd_assess(a: argparse.Namespace) -> int:
    pol = json.loads(Path(a.policy).read_text()) if a.policy else {}
    for k in ("mode",):
        if getattr(a, k):
            pol[k] = getattr(a, k)
    if a.org_account:
        pol["org_account_ids"] = a.org_account
    if a.internal_domain:
        pol["internal_domains"] = a.internal_domain
    if a.internal_cidr:
        pol["internal_cidrs"] = a.internal_cidr
    policy = policy_from(pol)
    dns = []
    for spec in a.dns or []:
        path, _, origin = spec.partition("@")
        dns.append((path, origin or None))
    repos = {}
    for spec in a.repo or []:
        label, _, d = spec.partition("=")
        if not d:
            label, d = Path(spec).name, spec
        if not Path(d).is_dir():
            raise ValueError(f"repository {d} is not a directory")
        repos[label] = d
    logs = [log_from(opts, path) for path, opts in map(_kv, a.log or [])]
    migrate = dict(m.split("=", 1) for m in a.migrate or [])
    inp = AssessmentInput(a.plan, dns, repos, logs, policy, parse_as_of(a.as_of), migrate)
    result = run(inp)
    rec = evidence.record(result, policy_dict(policy))
    Path(a.out).write_text(json.dumps(rec, indent=2))
    if a.markdown:
        Path(a.markdown).write_text(evidence.markdown(rec))
    g = rec["gate"]
    print(f"gate: {'PASS' if g['passed'] else 'FAIL'}  {g['verdict_counts']}")
    for r in rec["resources"]:
        print(f"  {r['verdict'].upper():16} {r['resource']['address']}  ({r['reasons'][0]})")
    print(f"evidence record: {a.out}")
    return 0 if g["passed"] else 2


def cmd_scan(a: argparse.Namespace) -> int:
    from .probes import live
    hosts: list[str] = []
    if a.hosts:
        hosts += Path(a.hosts).read_text().split()
    for spec in a.dns or []:
        path, _, origin = spec.partition("@")
        hosts += [r.name for r in dns_zone.load_any(path, origin or None) if r.type == "CNAME" or r.alias_target]
    findings = live.scan(hosts)
    out = [asdict(f) for f in findings]
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=2))
    bad = [f for f in findings if f.classification in ("reclaimable_candidate", "dangling_unregistered_domain")]
    for f in findings:
        if f.classification not in ("no_cname", "cname_resolves"):
            print(f"{f.classification:28} {f.hostname} -> {' -> '.join(f.chain)}  {f.detail}")
    print(f"{len(findings)} names checked, {len(bad)} reclaimable")
    return 3 if bad else 0


def cmd_serve(a: argparse.Namespace) -> int:
    import uvicorn
    uvicorn.run("retiresafe.api.app:app", host=a.host, port=a.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="retiresafe", description="Pre-flight checks for retiring cloud resources")
    ap.add_argument("--version", action="version", version=f"retiresafe {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("assess", help="assess a Terraform plan before it deletes resources")
    s.add_argument("--plan", required=True, help="output of `terraform show -json plan.out`")
    s.add_argument("--dns", action="append", help="Route 53 export JSON or BIND zone file (zone@origin)")
    s.add_argument("--repo", action="append", help="source tree to scan, label=dir")
    s.add_argument("--log", action="append", help="path,format=clf|s3|cloudfront[,host=..][,path_prefix=..][,covers=a|b]")
    s.add_argument("--policy", help="policy JSON file")
    s.add_argument("--mode", choices=["strict", "balanced"])
    s.add_argument("--org-account", action="append")
    s.add_argument("--internal-domain", action="append")
    s.add_argument("--internal-cidr", action="append")
    s.add_argument("--as-of", help="assessment time (ISO 8601 with timezone); default now")
    s.add_argument("--migrate", action="append", help="old_name=new_name for code rewrite patches")
    s.add_argument("--out", required=True)
    s.add_argument("--markdown")
    s.set_defaults(fn=cmd_assess)
    s = sub.add_parser("scan", help="live drift scan of DNS names you own")
    s.add_argument("--hosts")
    s.add_argument("--dns", action="append")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_scan)
    s = sub.add_parser("serve", help="run the REST API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    s.set_defaults(fn=cmd_serve)
    s = sub.add_parser("sources", help="print the source register behind every rule")
    s.set_defaults(fn=lambda a: print(json.dumps(SOURCES, indent=2)) or 0)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (ValueError, FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
