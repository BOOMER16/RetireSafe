"""Rollout and exception workflow: advisory mode, waivers, SARIF."""
import json
from datetime import datetime

import jsonschema
import pytest

from conftest import FIX, GEN, NASA_JULAUG, PILOT
from retiresafe.analysis.traffic import Policy
from retiresafe.cli import main as cli
from retiresafe.engine.assess import AssessmentInput, LogInput, run
from retiresafe.models import Verdict
from retiresafe.report import evidence, sarif
from retiresafe import waivers

AS_OF = datetime.fromisoformat("1995-09-01T03:59:53+00:00")
SCEN = json.loads((PILOT / "scenario.json").read_text(encoding="utf-8"))


def test_waiver_validation():
    ok, bad = waivers.load(inline=[
        {"resource": "a", "kind": "accept_reference", "reason": "r", "approved_by": "p", "expires": "1995-09-10"},
        {"resource": "a", "kind": "accept_reference", "reason": "r", "approved_by": "p", "expires": "1995-08-01"},
        {"resource": "a", "kind": "accept_reference", "reason": "r", "approved_by": "p", "expires": "1999-01-01"},
        {"resource": "a", "kind": "other", "reason": "r", "approved_by": "p", "expires": "1995-09-10"},
        {"resource": "a", "kind": "allow_release", "reason": "", "approved_by": "p", "expires": "1995-09-10"},
    ], as_of=AS_OF, max_days=90)
    assert len(ok) == 1
    assert [b["problem"].split(" ")[0] for b in bad] == ["expired", "expiry", "kind", "resource,"]


def test_advisory_mode_exit_code(tmp_path):
    out = tmp_path / "e.json"
    args = ["assess", "--plan", str(GEN / "plan_before.json"), "--out", str(out)]
    assert cli(args) == 2
    assert cli(args + ["--enforcement", "advisory"]) == 0
    g = json.loads(out.read_text(encoding="utf-8"))["gate"]
    assert g["passed"] and not g["would_pass"] and g["enforcement"] == "advisory"


def test_reference_waiver_and_sarif_schema(tmp_path):
    inline = [{"resource": "aws_s3_bucket.event_site", "kind": "accept_reference", "reference": "app::index.html:*",
               "reason": "link removed next release", "approved_by": "appsec", "expires": "1995-09-20"}]
    res = run(AssessmentInput(str(GEN / "plan_before.json"), [(str(GEN / "route53_before.json"), None)],
                              {"app": str(PILOT / "app")}, [], Policy(), AS_OF, {}, None, inline))
    site = next(a for a in res.resources if a.resource.address == "aws_s3_bucket.event_site")
    status = {r.location: p.status for r, p in zip(site.references, site.paths)}
    assert status["app::index.html:12"] == "waived" and site.waivers_applied
    rec = evidence.record(res, {"mode": "strict"})
    doc = sarif.build(rec, {"app": PILOT / "app"}, "infra/main.tf")
    jsonschema.validate(doc, json.loads((FIX / "sarif-schema-2.1.0.json").read_text(encoding="utf-8")))
    for r in doc["runs"][0]["results"]:            # GitHub-required properties
        loc = r["locations"][0]["physicalLocation"]
        assert r["message"]["text"] and r["partialFingerprints"] and loc["artifactLocation"]["uri"]
        assert {"startLine", "startColumn", "endLine", "endColumn"} <= set(loc["region"])
    code = [r for r in doc["runs"][0]["results"] if r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "index.html"]
    assert any(r["locations"][0]["physicalLocation"]["region"]["startLine"] == 14 for r in code)


@pytest.mark.realdata
@pytest.mark.skipif(not NASA_JULAUG.exists(), reason="needs the NASA Jul+Aug log")
def test_release_waiver_needs_evidence():
    logs = [LogInput(str(NASA_JULAUG), "clf", t["host"], [], t["path_prefix"]) for t in SCEN["traffic"]]
    w = [{"resource": "aws_s3_bucket.legacy_downloads", "kind": "allow_release", "reason": "mirror retired",
          "approved_by": "appsec", "expires": "1995-09-10"},
         {"resource": "aws_s3_bucket.event_assets", "kind": "allow_release", "reason": "please",
          "approved_by": "appsec", "expires": "1995-09-10"}]
    res = run(AssessmentInput(str(GEN / "plan_before.json"), [(str(GEN / "route53_before.json"), None)],
                              {"app": str(PILOT / "app")}, logs, Policy(internal_domains=["nasa.gov"]), AS_OF, {},
                              None, w))
    v = {a.resource.address: a.verdict for a in res.resources}
    assert v["aws_s3_bucket.legacy_downloads"] == Verdict.RELEASE      # quiet past quarantine: waiver applies
    assert v["aws_s3_bucket.event_assets"] == Verdict.BLOCK            # hijackable paths: waiver cannot release
