"""End-to-end: pilot scenario (real Terraform output), API, offline drift probe, research regression."""
import io
import json
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import BACKEND, GEN, NASA_JUL, NASA_JULAUG, PILOT
from retiresafe.analysis.traffic import Policy
from retiresafe.cli import main as cli
from retiresafe.engine.assess import AssessmentInput, LogInput, run
from retiresafe.models import Verdict
from retiresafe.probes import live
from retiresafe.report import evidence

SCEN = json.loads((PILOT / "scenario.json").read_text())
AS_OF = datetime.fromisoformat(SCEN["as_of"].replace("Z", "+00:00"))


def _verdicts(result):
    return {a.resource.address: a.verdict for a in result.resources}


def test_pilot_without_logs_never_releases_reclaimable_names():
    res = run(AssessmentInput(str(GEN / "plan_before.json"), [(str(GEN / "route53_before.json"), None)],
                              {"app": str(PILOT / "app")}, [], Policy(mode="balanced"), AS_OF))
    v = _verdicts(res)
    assert v["aws_s3_bucket.archive"] == Verdict.RELEASE            # account-regional: cannot be reclaimed
    for a in ("aws_s3_bucket.event_assets", "aws_s3_bucket.event_site", "aws_s3_bucket.legacy_downloads"):
        assert v[a] == Verdict.TOMBSTONE                            # consumers unknown without logs
    rec = evidence.record(res, {"mode": "balanced"})
    assert rec["gate"]["passed"] is False
    assert rec["schema"] == "retiresafe.evidence/v1"
    assert all("sha256" in i or "sha256_tree" in i for i in rec["inputs"])


@pytest.mark.realdata
@pytest.mark.skipif(not NASA_JULAUG.exists(), reason="needs the combined NASA Jul+Aug 1995 log")
def test_pilot_full_story_with_real_traffic(tmp_path):
    logs = [LogInput(str(NASA_JULAUG), "clf", t["host"], [], t["path_prefix"]) for t in SCEN["traffic"]]
    before = run(AssessmentInput(str(GEN / "plan_before.json"), [(str(GEN / "route53_before.json"), None)],
                                 {"app": str(PILOT / "app")}, logs, Policy(mode="strict",
                                 org_account_ids=["123456789012"], internal_domains=["nasa.gov"]), AS_OF,
                                 SCEN["migrate_to"]))
    v = _verdicts(before)
    assert v["aws_s3_bucket.event_assets"] == Verdict.BLOCK
    assert v["aws_s3_bucket.event_site"] == Verdict.BLOCK
    assert v["aws_s3_bucket.legacy_downloads"] == Verdict.TOMBSTONE
    assert v["aws_s3_bucket.archive"] == Verdict.RELEASE
    assets = next(a for a in before.resources if a.resource.address == "aws_s3_bucket.event_assets")
    status = {r.location: p.status for r, p in zip(assets.references, assets.paths)}
    assert status["app::index.html:14"] == "hijackable"          # unpinned script
    assert status["app::index.html:7"] == "safe"                 # SRI-pinned stylesheet
    assert status["app::tools/upload_assets.py:10"] == "safe"    # ExpectedBucketOwner
    legacy = next(a for a in before.resources if a.resource.address == "aws_s3_bucket.legacy_downloads")
    t = legacy.traffic[0]
    assert t.requests == 87 and t.silence_days > t.quarantine_days_conservative   # real quiet period


def test_cli_gate_exit_codes(tmp_path):
    out = tmp_path / "e.json"
    code = cli(["assess", "--plan", str(GEN / "plan_after.json"), "--dns", str(GEN / "route53_after.json"),
                "--out", str(out), "--as-of", SCEN["as_of"]])
    assert code == 0 and json.loads(out.read_text())["gate"]["passed"]
    code = cli(["assess", "--plan", str(GEN / "plan_before.json"), "--out", str(out)])
    assert code == 2
    assert cli(["assess", "--plan", str(BACKEND / "pyproject.toml"), "--out", str(out)]) == 1   # not a plan


# ---------- API ----------
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RETIRESAFE_DB", str(tmp_path / "t.db"))
    from retiresafe.api import app as appmod
    appmod._store = None
    return TestClient(appmod.app)


def _repo_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for p in (PILOT / "app").rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(PILOT / "app"))
    return buf.getvalue()


def test_api_assessment_roundtrip(client):
    files = [("plan", ("plan_before.json", (GEN / "plan_before.json").read_bytes())),
             ("dns", ("route53_before.json", (GEN / "route53_before.json").read_bytes())),
             ("repo", ("app.zip", _repo_zip()))]
    r = client.post("/v1/assessments", files=files,
                    data={"config": json.dumps({"policy": {"mode": "strict"}, "as_of": SCEN["as_of"]})})
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["gate"]["passed"] is False
    aid = rec["assessment_id"]
    assert client.get(f"/v1/assessments/{aid}").json()["assessment_id"] == aid
    assert client.get("/v1/assessments").json()[0]["assessment_id"] == aid
    assert "Gate: FAIL" in client.get(f"/v1/assessments/{aid}/report.md").text
    assert client.get("/v1/assessments/nope").status_code == 404
    k = client.get("/v1/knowledge").json()
    assert "aws_s3_bucket" in k["name_bearing_resource_types"]


def test_api_rejects_bad_input(client, monkeypatch):
    plan = ("plan", ("p.json", (GEN / "plan_before.json").read_bytes()))
    assert client.post("/v1/assessments", files=[plan], data={"config": "{not json"}).status_code == 400
    assert client.post("/v1/assessments", files=[plan],
                       data={"config": json.dumps({"policy": {"alpha": 2}})}).status_code == 422
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../evil.txt", "x")
    r = client.post("/v1/assessments", files=[plan, ("repo", ("r.zip", buf.getvalue()))])
    assert r.status_code == 400 and "escapes" in r.text
    monkeypatch.setenv("RETIRESAFE_API_KEY", "s3cret")
    assert client.get("/v1/knowledge").status_code == 401
    assert client.get("/v1/knowledge", headers={"X-API-Key": "s3cret"}).status_code == 200


# ---------- drift probe (offline: DNS and S3 answers are stubbed) ----------
def _stub(monkeypatch, answers: dict, s3_state: str = "missing"):
    def q(res, name, rtype, retries=2):
        return answers.get((name, rtype), ("NOANSWER", []))
    monkeypatch.setattr(live, "query", q)
    monkeypatch.setattr(live, "s3_bucket_state", lambda b, s=None: s3_state)


def test_drift_probe_ladder(monkeypatch):
    _stub(monkeypatch, {("a.corp.example", "CNAME"): ("OK", ["a-bucket.s3.amazonaws.com."]),
                        ("a-bucket.s3.amazonaws.com", "A"): ("OK", ["52.0.0.1"])})
    assert live.check_hostname("a.corp.example").classification == "reclaimable_candidate"
    _stub(monkeypatch, {("a.corp.example", "CNAME"): ("OK", ["a-bucket.s3.amazonaws.com."]),
                        ("a-bucket.s3.amazonaws.com", "A"): ("OK", ["52.0.0.1"])}, "exists:403")
    assert live.check_hostname("a.corp.example").classification == "cname_resolves"
    _stub(monkeypatch, {("b.corp.example", "CNAME"): ("OK", ["gone-app.azurewebsites.net."]),
                        ("gone-app.azurewebsites.net", "A"): ("NXDOMAIN", []),
                        ("gone-app.azurewebsites.net", "AAAA"): ("NXDOMAIN", []),
                        ("azurewebsites.net", "NS"): ("OK", ["ns1."])})
    assert live.check_hostname("b.corp.example").classification == "reclaimable_candidate"


def test_drift_probe_timeout_is_never_reported_clean(monkeypatch):
    # regression: a timed-out CNAME lookup used to be classified as "no_cname"
    _stub(monkeypatch, {("c.corp.example", "CNAME"): ("TIMEOUT", []), ("c.corp.example", "A"): ("OK", ["1.2.3.4"])})
    assert live.check_hostname("c.corp.example").classification == "lookup_error"


# ---------- regression against the research test beds (same real data) ----------
@pytest.mark.realdata
@pytest.mark.skipif(not NASA_JUL.exists(), reason="needs NASA_access_log_Jul95")
def test_reproduces_research_tb2_and_tb3():
    import sys
    sys.path.insert(0, str(BACKEND / "validation"))
    import cross_check
    assert cross_check.check_tb2(NASA_JUL)["match"]
    assert cross_check.check_tb3(NASA_JUL)["match"]
