"""Submit demo steps to a running RetireSafe server over HTTP, exactly as the console's form does.

    python demo/run_steps.py                 # steps 01-04 to http://127.0.0.1:8080
    python demo/run_steps.py 02 04           # only these steps
    python demo/run_steps.py --server http://127.0.0.1:8090 --api-key KEY

Nothing is pre-recorded: every step uploads its inputs and the server runs a fresh assessment.
Use it as a fallback when uploading the 373 MB traffic log through the browser is slow.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_demo_kit import KIT, LOG_NAME, ROOT, RUNS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("steps", nargs="*", help="step prefixes, e.g. 01 02 (default: 01-04)")
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--api-key")
    ap.add_argument("--log", default=str(ROOT / "data" / "nasa-http" / LOG_NAME))
    a = ap.parse_args()
    wanted = [r for r in RUNS if not r[0].startswith("expert/") and (not a.steps or any(r[0].startswith(s) for s in a.steps))]
    headers = {"X-API-Key": a.api_key} if a.api_key else {}
    try:
        requests.get(f"{a.server}/healthz", timeout=5).raise_for_status()
    except requests.RequestException as e:
        print(f"server not reachable at {a.server} ({e}); start it with: retiresafe serve")
        return 1
    worst = 0
    for name, plan_dir, app_zip, set_dir, needs_log in wanted:
        if needs_log and not Path(a.log).exists():
            print(f"{name}: traffic log not found at {a.log}; run: python scripts/get_data.py")
            return 1
        cfg = (KIT / set_dir / "settings.json").read_text(encoding="utf-8")
        handles = [open(KIT / plan_dir / "plan.json", "rb"), open(KIT / plan_dir / "route53.json", "rb"), open(KIT / app_zip, "rb")]
        files = [("plan", ("plan.json", handles[0])), ("dns", ("route53.json", handles[1])), ("repo", ("app.zip", handles[2]))]
        if needs_log:
            handles.append(open(a.log, "rb"))
            files.append(("logs", (LOG_NAME, handles[-1])))
        print(f"{name}: uploading{' (with the 373 MB traffic log)' if needs_log else ''} ...", flush=True)
        t0 = time.time()
        try:
            r = requests.post(f"{a.server}/v1/assessments", files=files, data={"config": cfg}, headers=headers, timeout=1800)
        finally:
            for h in handles:
                h.close()
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:300]}")
            return 1
        rec = r.json()
        g = rec["gate"]
        worst = max(worst, 0 if g["passed"] else 2)
        print(f"  gate {'PASS' if g['passed'] else 'FAIL'}  {g['verdict_counts']}  ({time.time() - t0:.0f} s)")
        print(f"  {a.server}/ui/#/a/{rec['assessment_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
