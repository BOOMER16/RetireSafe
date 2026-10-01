"""Run the pilot scenario end to end and write results to pilot/results/.

1. BEFORE  : proposed deletion (plan_before) + DNS v1 + original app + real traffic  -> strict and balanced
2. PATCH   : apply the code diff RetireSafe produced (migrate assets to an account-regional bucket)
3. AFTER   : tombstone plan (plan_after) + DNS v2 + patched app + same traffic      -> strict

Traffic is the real NASA-HTTP Jul+Aug 1995 log (unmodified lines), attributed to the scenario
hosts as defined in pilot/scenario.json.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PILOT.parent / "backend"))
from retiresafe.cli import main as cli  # noqa: E402

SCEN = json.loads((PILOT / "scenario.json").read_text())
G, R = PILOT / "generated", PILOT / "results"


def log_args(log_path: str) -> list[str]:
    out = []
    for lg in SCEN["traffic"]:
        out += ["--log", f"{log_path},format=clf,host={lg['host']},path_prefix={lg['path_prefix']}"]
    return out


def assess(tag: str, plan: str, dns: str, repo: Path, mode: str, log_path: str) -> dict:
    args = ["assess", "--plan", str(G / plan), "--dns", str(G / dns), "--repo", f"app={repo}",
            *log_args(log_path), "--mode", mode, "--org-account", SCEN["org_account_id"],
            "--internal-domain", SCEN["internal_domain"], "--as-of", SCEN["as_of"],
            "--out", str(R / f"{tag}.json"), "--markdown", str(R / f"{tag}.md")]
    for old, new in SCEN.get("migrate_to", {}).items():
        args += ["--migrate", f"{old}={new}"]
    code = cli(args)
    rec = json.loads((R / f"{tag}.json").read_text())
    return {"exit_code": code, "gate": rec["gate"],
            "verdicts": {r["resource"]["address"]: r["verdict"] for r in rec["resources"]}}


def main() -> None:
    log_path = sys.argv[1] if len(sys.argv) > 1 else SCEN["traffic_log_default"]
    R.mkdir(exist_ok=True)
    summary = {}
    summary["before_strict"] = assess("before_strict", "plan_before.json", "route53_before.json",
                                      PILOT / "app", "strict", log_path)
    summary["before_balanced"] = assess("before_balanced", "plan_before.json", "route53_before.json",
                                        PILOT / "app", "balanced", log_path)
    # apply RetireSafe's own code patch to a copy of the app
    after_app = PILOT / ".work" / "app_after"
    shutil.rmtree(after_app, ignore_errors=True)
    shutil.copytree(PILOT / "app", after_app)
    rec = json.loads((R / "before_strict.json").read_text())
    diffs = [p["content"] for r in rec["resources"] for p in r["patches"] if p["kind"] == "code_diff"]
    (R / "applied_code.patch").write_text("".join(diffs))
    subprocess.run(["git", "apply", "--unsafe-paths", "-p1", str(R / "applied_code.patch")], cwd=after_app,
                   check=True)
    summary["after_strict"] = assess("after_strict", "plan_after.json", "route53_after.json", after_app,
                                     "strict", log_path)
    (R / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
