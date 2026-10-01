"""Secrets must never reach evidence records, reports or the database.

The pilot plan is real `terraform show -json` output that contains a SecureString canary in plain
text (Terraform documents this behaviour); the pilot app contains AWS's documented example keys.
"""
import json

import pytest
from fastapi.testclient import TestClient

from conftest import GEN, PILOT
from retiresafe import redact
from retiresafe.analysis.traffic import Policy
from retiresafe.engine.assess import AssessmentInput, run
from retiresafe.report import evidence

CANARIES = ["RS-CANARY-db-password-7f3c9a", "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"]


def test_canary_really_is_in_the_terraform_plan():
    # guards the test itself: the input must contain the secret in plain text
    assert CANARIES[0] in (GEN / "plan_before.json").read_text(encoding="utf-8")


def test_no_secret_in_evidence_or_markdown():
    res = run(AssessmentInput(str(GEN / "plan_before.json"), [(str(GEN / "route53_before.json"), None)],
                              {"app": str(PILOT / "app")}, [], Policy(org_account_ids=["123456789012"])))
    rec = evidence.record(res, {"mode": "strict"})
    blob = json.dumps(rec) + evidence.markdown(rec)
    for c in CANARIES:
        assert c not in blob, c
    # the references themselves survive redaction
    texts = [r["text"] for x in rec["resources"] for r in x["references"]]
    assert any("[sensitive value; contains a reference to rs-pilot-event-assets-2025]" in t for t in texts)
    assert any("[REDACTED] aws s3 sync s3://rs-pilot-legacy-downloads" in t for t in texts)
    ssm = next(x for x in rec["resources"] if x["resource"]["address"] == "aws_ssm_parameter.legacy_db_password")
    assert "value" not in ssm["resource"]["attributes"]


def test_no_secret_in_api_database(tmp_path, monkeypatch):
    monkeypatch.setenv("RETIRESAFE_DB", str(tmp_path / "t.db"))
    from retiresafe.api import app as appmod
    appmod._store = None
    c = TestClient(appmod.app)
    r = c.post("/v1/assessments", files=[("plan", ("p.json", (GEN / "plan_before.json").read_bytes()))])
    assert r.status_code == 200
    raw = (tmp_path / "t.db").read_bytes()
    for c_ in CANARIES:
        assert c_.encode() not in raw


@pytest.mark.parametrize("line,secret", [
    ("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE"),
    ("aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'", "wJalrXUtnFEMI"),
    ('GITHUB_TOKEN="ghp_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"', "ghp_a1B2"),
    ("-----BEGIN RSA PRIVATE KEY-----\n" + "MIIEowIBAAKCAQEA7" * 6 + "\n-----END RSA PRIVATE KEY-----", "MIIEow"),
])
def test_scrub_removes_secrets(line, secret):
    assert secret not in redact.scrub(line)


@pytest.mark.parametrize("line", [
    '<script src="https://rs-pilot-event-assets-2025.s3.amazonaws.com/js/countdown.js"></script>',
    's3.put_object(Bucket="rs-pilot-event-assets-2025", Key=key, ExpectedBucketOwner=ACCOUNT_ID)',
    'resource "aws_s3_bucket" "logs" { bucket = "acme-prod-logs-2024" }',
])
def test_scrub_keeps_ordinary_reference_lines(line):
    assert redact.scrub(line) == line


def test_mask_helpers():
    vals = {"name": "p", "value": "secret", "tags": {"a": "b"}, "list": [{"k": "s"}, {"k": "t"}]}
    mask = {"value": True, "list": [{"k": True}, {}]}
    out = redact.by_mask(vals, mask)
    assert out["value"] == redact.SENSITIVE and out["name"] == "p" and out["list"][0]["k"] == redact.SENSITIVE
    assert out["list"][1]["k"] == "t"
    assert redact.mask_at(mask, ["list", "0", "k"]) and not redact.mask_at(mask, ["name"])


def test_rule_loading_is_reported():
    rules, info = redact.rules()
    assert info["loaded"] >= 200 and info["commit"].startswith("b58d3f102cf3")
