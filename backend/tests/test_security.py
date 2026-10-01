"""Hardening of the service itself: auth, archive limits, scope guard, retention, headers."""
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import GEN
from retiresafe import ownership
from retiresafe.cli import main as cli


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("RETIRESAFE_DB", str(tmp_path / "t.db"))
    from retiresafe.api import app as appmod
    appmod._store = None
    return appmod, TestClient(appmod.app)


def _plan():
    return ("plan", ("p.json", (GEN / "plan_after.json").read_bytes()))


def test_archive_bomb_is_refused(api, monkeypatch):
    appmod, c = api
    monkeypatch.setattr(appmod, "MAX_EXTRACT", 1024 * 1024)          # 1 MB limit for the test
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("big.txt", "0" * (5 * 1024 * 1024))               # 5 MB that compresses to ~5 KB
    assert len(buf.getvalue()) < 64 * 1024
    r = c.post("/v1/assessments", files=[_plan(), ("repo", ("r.zip", buf.getvalue()))])
    assert r.status_code == 413


def test_scan_scope_guard(api, monkeypatch):
    _, c = api
    monkeypatch.delenv("RETIRESAFE_OWNED_DOMAINS", raising=False)
    assert c.post("/v1/drift-scans", json={"hostnames": ["a.example.org"]}).status_code == 403
    monkeypatch.setenv("RETIRESAFE_OWNED_DOMAINS", "corp.example")
    assert c.post("/v1/drift-scans", json={"hostnames": ["victim.example.org"]}).status_code == 422
    assert ownership.split(["x.corp.example", "corp.example", "evilcorp.example"], ["corp.example"]) == \
        (["x.corp.example", "corp.example"], ["evilcorp.example"])


def test_delete_and_retention(api, monkeypatch):
    appmod, c = api
    rec = c.post("/v1/assessments", files=[_plan()]).json()
    assert c.delete(f"/v1/assessments/{rec['assessment_id']}").json() == {"deleted": rec["assessment_id"]}
    assert c.get(f"/v1/assessments/{rec['assessment_id']}").status_code == 404
    old = dict(rec, assessment_id="old-one",
               created_at=(datetime.now(timezone.utc) - timedelta(days=400)).isoformat())
    appmod.store().put_assessment(old)          # inserted, then purged by the next insert
    monkeypatch.setenv("RETIRESAFE_RETENTION_DAYS", "90")
    assert appmod.store().purge() == 1


def test_headers_and_constant_time_auth(api, monkeypatch):
    _, c = api
    monkeypatch.setenv("RETIRESAFE_API_KEY", "k3y")
    r = c.get("/v1/knowledge", headers={"X-API-Key": "k3y"})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert c.get("/v1/knowledge", headers={"X-API-Key": "wrong"}).status_code == 401


def test_serve_refuses_public_bind_without_key(monkeypatch, capsys):
    monkeypatch.delenv("RETIRESAFE_API_KEY", raising=False)
    assert cli(["serve", "--host", "0.0.0.0"]) == 1
    assert "refusing" in capsys.readouterr().err


def test_cli_scan_requires_owned_domain(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("RETIRESAFE_OWNED_DOMAINS", raising=False)
    hosts = tmp_path / "h.txt"
    hosts.write_text("www.example.org\n", encoding="utf-8")
    assert cli(["scan", "--hosts", str(hosts)]) == 1
