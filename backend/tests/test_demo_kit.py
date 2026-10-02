"""The demo kit must stay consistent with the code: files intact, recorded results reproducible."""
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

KIT = Path(__file__).resolve().parents[2] / "demo" / "kit"
pytestmark = pytest.mark.skipif(not (KIT / "MANIFEST.json").is_file(), reason="needs a repository checkout")


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("RETIRESAFE_DB", str(tmp_path / "kit.db"))
    from retiresafe.api import app as appmod
    appmod._store = None
    return appmod, TestClient(appmod.app)


def _post(c, plan_dir, app_zip, settings_dir):
    files = [("plan", ("plan.json", (KIT / plan_dir / "plan.json").read_bytes())),
             ("dns", ("route53.json", (KIT / plan_dir / "route53.json").read_bytes())),
             ("repo", ("app.zip", (KIT / app_zip).read_bytes()))]
    return c.post("/v1/assessments", files=files, data={"config": (KIT / settings_dir / "settings.json").read_text(encoding="utf-8")})


def test_manifest_matches_files():
    man = json.loads((KIT / "MANIFEST.json").read_text(encoding="utf-8"))["files"]
    for rel, digest in man.items():
        assert hashlib.sha256((KIT / rel).read_bytes()).hexdigest() == digest, rel


def test_step01_reproduces_recorded_result(api):
    _, c = api
    rec = _post(c, "01_proposed_change", "01_proposed_change/app.zip", "01_proposed_change").json()
    expected = json.loads((KIT / "EXPECTED.json").read_text(encoding="utf-8"))["01_proposed_change"]
    assert rec["gate"]["passed"] is expected["gate_passed"]
    assert rec["gate"]["verdict_counts"] == expected["verdict_counts"]
    assert {r["resource"]["address"]: r["verdict"] for r in rec["resources"]} == \
        {a: v["verdict"] for a, v in expected["resources"].items()}
    assert rec["label"].startswith("01 ")


def test_settings_files_are_valid_api_config():
    from retiresafe.config import policy_from
    for f in KIT.glob("*/settings.json"):
        cfg = json.loads(f.read_text(encoding="utf-8"))
        policy_from(cfg["policy"])
        assert cfg["as_of"] and cfg["label"]


def test_hostile_archives_are_refused(api, monkeypatch):
    appmod, c = api
    r = _post(c, "01_proposed_change", "expert/E_zip_slip/app.zip", "01_proposed_change")
    assert r.status_code == 400 and "escapes" in r.json()["detail"]
    monkeypatch.setattr(appmod, "MAX_EXTRACT", 1024 * 1024)
    r = _post(c, "01_proposed_change", "expert/F_archive_bomb/app.zip", "01_proposed_change")
    assert r.status_code == 413
