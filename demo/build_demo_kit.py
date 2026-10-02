"""Build the demo kit (demo/kit/) and record what every scenario actually produces.

    python demo/build_demo_kit.py            # write the kit files (fast)
    python demo/build_demo_kit.py --verify   # also run every scenario through the API and write
                                             # demo/kit/EXPECTED.md + EXPECTED.json (needs the NASA log)

Every input comes from the pilot, which is real tool output:
  * Terraform 1.16.4 / hashicorp/aws 6.67.0 plans and Route 53 exports (pilot/generated)
  * the pilot application code (pilot/app); the "corrected" copy is produced by applying RetireSafe's own
    code patch (pilot/results/applied_code.patch) with retiresafe.engine.apply_patch
  * real traffic: NASA-HTTP Jul+Aug 1995 (data/nasa-http/nasa_jul_aug_1995.log, from scripts/get_data.py)
The expert variants change one thing each in the application code, so a tester can see one condition move.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

KIT = ROOT / "demo" / "kit"
GEN = ROOT / "pilot" / "generated"
APP = ROOT / "pilot" / "app"
PATCH = ROOT / "pilot" / "results" / "applied_code.patch"
SCEN = json.loads((ROOT / "pilot" / "scenario.json").read_text(encoding="utf-8"))
LOG_NAME = "nasa_jul_aug_1995.log"
FIXED_TIME = (2026, 10, 1, 0, 0, 0)          # deterministic zips


def zip_tree(src: Path, dest: Path, edits: dict[str, bytes] | None = None, extra: dict[str, bytes] | None = None) -> None:
    edits, extra = edits or {}, extra or {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        names = sorted(p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for n in names:
            data = edits.get(n, (src / n).read_bytes())
            z.writestr(zipfile.ZipInfo(n, FIXED_TIME), data, zipfile.ZIP_DEFLATED)
        for n, data in sorted(extra.items()):
            z.writestr(zipfile.ZipInfo(n, FIXED_TIME), data, zipfile.ZIP_DEFLATED)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(buf.getvalue())


def settings(label: str, mode: str = "strict", logs: bool = False) -> dict:
    cfg = {"label": label, "repo_label": "app", "as_of": SCEN["as_of"],
           "policy": {"mode": mode, "enforcement": "enforce", "org_account_ids": [SCEN["org_account_id"]]},
           "migrate_to": SCEN["migrate_to"]}
    if logs:
        cfg["policy"]["internal_domains"] = [SCEN["internal_domain"]]
        cfg["logs"] = [{"filename": LOG_NAME, "format": "clf", "host": t["host"], "path_prefix": t["path_prefix"]}
                       for t in SCEN["traffic"]]
    return cfg


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def build() -> None:
    from retiresafe.engine import apply_patch

    if KIT.exists():
        for p in KIT.iterdir():
            if p.name not in ("EXPECTED.md", "EXPECTED.json"):
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    KIT.mkdir(parents=True, exist_ok=True)

    s1 = KIT / "01_proposed_change"
    s1.mkdir(parents=True)
    shutil.copy(GEN / "plan_before.json", s1 / "plan.json")
    shutil.copy(GEN / "route53_before.json", s1 / "route53.json")
    zip_tree(APP, s1 / "app.zip")
    write_json(s1 / "settings.json", settings("01 · Proposed deletion · strict · no logs"))

    write_json(KIT / "02_add_real_traffic" / "settings.json", settings("02 · Proposed deletion · strict · real traffic", logs=True))
    write_json(KIT / "03_balanced_policy" / "settings.json", settings("03 · Proposed deletion · balanced · real traffic", "balanced", logs=True))

    s4 = KIT / "04_corrected_change"
    s4.mkdir(parents=True)
    shutil.copy(GEN / "plan_after.json", s4 / "plan.json")
    shutil.copy(GEN / "route53_after.json", s4 / "route53.json")
    with tempfile.TemporaryDirectory() as tmp:
        fixed = Path(tmp) / "app"
        shutil.copytree(APP, fixed)
        apply_patch.apply(PATCH.read_text(encoding="utf-8"), fixed)       # RetireSafe's own code patch
        zip_tree(fixed, s4 / "app.zip")
    write_json(s4 / "settings.json", settings("04 · Corrected change · strict · real traffic", logs=True))

    # ---- expert variants: one change each, against step 02 inputs ----
    html_ = (APP / "index.html").read_text(encoding="utf-8")
    js = (APP / "js" / "countdown.js").read_bytes()
    sri = "sha384-" + base64.b64encode(hashlib.sha384(js).digest()).decode()     # real hash of the real file
    script = '<script src="https://rs-pilot-event-assets-2025.s3.amazonaws.com/js/countdown.js"></script>'
    assert script in html_, "pilot app changed; update the expert variants"
    ex = KIT / "expert"
    zip_tree(APP, ex / "A_pin_script_with_sri" / "app.zip", edits={"index.html": html_.replace(
        script, f'<script src="https://rs-pilot-event-assets-2025.s3.amazonaws.com/js/countdown.js" integrity="{sri}" crossorigin="anonymous"></script>').encode()})
    up = (APP / "tools" / "upload_assets.py").read_text(encoding="utf-8")
    assert ", ExpectedBucketOwner=ACCOUNT_ID" in up
    zip_tree(APP, ex / "B_drop_owner_check" / "app.zip", edits={"tools/upload_assets.py": up.replace(", ExpectedBucketOwner=ACCOUNT_ID", "").encode()})
    zip_tree(APP, ex / "C_comment_out_script" / "app.zip", edits={"index.html": html_.replace(script, f"<!-- {script} -->").encode()})
    zip_tree(APP, ex / "D_hostile_markup" / "app.zip", extra={"docs/notes.html": (
        '<p>Mirror: <a href="https://rs-pilot-event-assets-2025.s3.amazonaws.com/archive/">assets</a>'
        '<img src=x onerror="alert(document.domain)"><script>alert(1)</script></p>\n').encode()})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("../../outside.txt", FIXED_TIME), b"zip-slip probe\n")
    (ex / "E_zip_slip").mkdir(parents=True)
    (ex / "E_zip_slip" / "app.zip").write_bytes(buf.getvalue())

    bomb = io.BytesIO()                       # 5 MB of zeros that compresses to ~5 KB
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("big.txt", FIXED_TIME), b"0" * (5 * 1024 * 1024), zipfile.ZIP_DEFLATED)
    (ex / "F_archive_bomb").mkdir(parents=True)
    (ex / "F_archive_bomb" / "app.zip").write_bytes(bomb.getvalue())

    manifest = {str(p.relative_to(KIT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(KIT.rglob("*")) if p.is_file() and p.name not in ("EXPECTED.md", "EXPECTED.json", "MANIFEST.json")}
    write_json(KIT / "MANIFEST.json", {"note": "sha256 of every kit file; inputs come from pilot/ (real tool output)",
                                       "sri_of_js_countdown": sri, "files": manifest})
    print(f"kit written to {KIT}")


# ---------------- verification ----------------
RUNS = [  # (name, folder with plan/dns, app zip, settings folder)
    ("01_proposed_change", "01_proposed_change", "01_proposed_change/app.zip", "01_proposed_change", False),
    ("02_add_real_traffic", "01_proposed_change", "01_proposed_change/app.zip", "02_add_real_traffic", True),
    ("03_balanced_policy", "01_proposed_change", "01_proposed_change/app.zip", "03_balanced_policy", True),
    ("04_corrected_change", "04_corrected_change", "04_corrected_change/app.zip", "04_corrected_change", True),
    ("expert/A_pin_script_with_sri", "01_proposed_change", "expert/A_pin_script_with_sri/app.zip", "02_add_real_traffic", True),
    ("expert/B_drop_owner_check", "01_proposed_change", "expert/B_drop_owner_check/app.zip", "02_add_real_traffic", True),
    ("expert/C_comment_out_script", "01_proposed_change", "expert/C_comment_out_script/app.zip", "02_add_real_traffic", True),
    ("expert/D_hostile_markup", "01_proposed_change", "expert/D_hostile_markup/app.zip", "02_add_real_traffic", True),
    ("expert/E_zip_slip", "01_proposed_change", "expert/E_zip_slip/app.zip", "01_proposed_change", False),
]


def verify(log_path: Path) -> None:
    import os
    import time
    from fastapi.testclient import TestClient

    tmp = tempfile.mkdtemp()
    os.environ["RETIRESAFE_DB"] = str(Path(tmp) / "verify.db")
    from retiresafe.api import app as appmod
    appmod._store = None
    c = TestClient(appmod.app)
    out = {}
    for name, plan_dir, app_zip, set_dir, needs_log in RUNS:
        cfg = json.loads((KIT / set_dir / "settings.json").read_text(encoding="utf-8"))
        cfg["label"] = cfg["label"] if not name.startswith("expert/") else f"expert · {name.split('/')[1]}"
        files = [("plan", ("plan.json", (KIT / plan_dir / "plan.json").read_bytes())),
                 ("dns", ("route53.json", (KIT / plan_dir / "route53.json").read_bytes())),
                 ("repo", ("app.zip", (KIT / app_zip).read_bytes()))]
        fh = open(log_path, "rb") if needs_log else None
        if fh:
            files.append(("logs", (LOG_NAME, fh)))
        t0 = time.time()
        r = c.post("/v1/assessments", files=files, data={"config": json.dumps(cfg)})
        if fh:
            fh.close()
        took = round(time.time() - t0, 1)
        if r.status_code != 200:
            out[name] = {"http_status": r.status_code, "detail": r.json().get("detail"), "seconds": took}
            print(f"{name:34s} HTTP {r.status_code}: {r.json().get('detail')}")
            continue
        rec = r.json()
        res = {}
        for x in rec["resources"]:
            paths = {}
            for p in x["paths"]:
                ref = next((y for y in x["references"] if y["id"] == p["reference_id"]), {})
                paths[ref.get("location", p["reference_id"])] = p["status"] + (f" (breaks at {','.join(p['broken_by'])})" if p["broken_by"] else "")
            res[x["resource"]["address"]] = {"verdict": x["verdict"], "paths": paths}
        out[name] = {"label": rec.get("label"), "gate_passed": rec["gate"]["passed"],
                     "cli_exit_code": 0 if rec["gate"]["passed"] else 2,
                     "verdict_counts": rec["gate"]["verdict_counts"], "resources": res, "seconds": took}
        print(f"{name:34s} gate {'PASS' if rec['gate']['passed'] else 'FAIL'} {rec['gate']['verdict_counts']} ({took}s)")
    write_json(KIT / "EXPECTED.json", out)
    md = ["# Expected results (recorded by `python demo/build_demo_kit.py --verify`)", "",
          "Produced by running every scenario through the same API the console uses. "
          "Times are from the build machine; a laptop may differ.", ""]
    for name, v in out.items():
        md.append(f"## {name}")
        if "http_status" in v:
            md += [f"* **HTTP {v['http_status']}**: {v['detail']}", ""]
            continue
        md.append(f"* Gate **{'PASS' if v['gate_passed'] else 'FAIL'}** (CLI exit {v['cli_exit_code']}), "
                  f"verdicts {v['verdict_counts']}, {v['seconds']} s")
        for addr, rv in v["resources"].items():
            md.append(f"* `{addr}` → **{rv['verdict']}**")
            for loc, st in rv["paths"].items():
                md.append(f"  * `{loc}`: {st}")
        md.append("")
    (KIT / "EXPECTED.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {KIT / 'EXPECTED.md'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--log", default=str(ROOT / "data" / "nasa-http" / LOG_NAME))
    a = ap.parse_args()
    build()
    if a.verify:
        log = Path(a.log)
        if not log.exists():
            sys.exit(f"traffic log not found: {log}\nrun: python scripts/get_data.py")
        verify(log)


if __name__ == "__main__":
    main()
