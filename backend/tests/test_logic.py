"""Names, provider rules, statistics and the five-condition logic."""
import json
import math
from datetime import datetime, timedelta, timezone

import pytest
from scipy.stats import chi2

from conftest import FIX
from retiresafe import names
from retiresafe.analysis.traffic import Policy, quarantine_days, rate_bounds, summarise
from retiresafe.collectors import terraform_plan
from retiresafe.collectors.access_logs import Request
from retiresafe.engine import decide
from retiresafe.knowledge import providers
from retiresafe.models import ConditionResult, Reference, RefKind, RetiringResource, Tri, Verdict


# ---------- names ----------
@pytest.mark.parametrize("text,expected", [
    ("https://my.bucket.s3.us-east-1.amazonaws.com/x", {"my.bucket"}),
    ("https://s3.amazonaws.com/other-bkt/key", {"other-bkt"}),
    ("aws s3 cp s3://third-bkt/a .", {"third-bkt"}),
    ('"Resource": "arn:aws:s3:::fourth-bkt/*"', {"fourth-bkt"}),
    ('s3.get_object(Bucket="fifth-bkt", Key=k)', {"fifth-bkt"}),
    ("https://bkt.s3-website-us-east-1.amazonaws.com", {"bkt"}),
    ("https://example.com/no/bucket/here", set()),
])
def test_s3_bucket_extraction(text, expected):
    assert names.s3_buckets_in(text) == expected


@pytest.mark.parametrize("target,expected", [
    ("bkt1.s3.amazonaws.com", "bkt1"),
    ("s3-website-us-east-1.amazonaws.com", "a.example.com"),   # bare endpoint: S3 uses the Host header
    ("s3-us-west-2.amazonaws.com", "a.example.com"),
    ("cdn.example.net", None),
])
def test_bucket_from_dns(target, expected):
    assert names.bucket_from_dns("a.example.com", target) == expected


# ---------- provider rules ----------
def test_s3_namespace_rules():
    g = providers.view("aws_s3_bucket", {"bucket": "b-bkt", "bucket_namespace": "global"}, "us-east-1")
    a = providers.view("aws_s3_bucket", {"bucket": "p-123456789012-us-east-1-an",
                                         "bucket_namespace": "account-regional"}, "us-east-1")
    u = providers.view("aws_s3_bucket", {"bucket": "p-123456789012-us-east-1-an"}, "us-east-1")
    d = providers.view("aws_s3_bucket", {"bucket": "plain-bkt"}, "us-east-1")
    assert (g.reclaimable.value, a.reclaimable.value, u.reclaimable.value, d.reclaimable.value) == \
        (Tri.TRUE, Tri.FALSE, Tri.UNKNOWN, Tri.TRUE)
    assert "src:aws-sdk-s3-account-regional" in a.reclaimable.evidence_ids


def test_account_regional_name_format_matches_sdk_example():
    # example quoted in the AWS SDK model: amzn-s3-demo-bucket-111122223333-us-west-2-an
    m = providers.ACCOUNT_REGIONAL_NAME.match("amzn-s3-demo-bucket-111122223333-us-west-2-an")
    assert m and m["account"] == "111122223333" and m["region"] == "us-west-2"


def test_azure_and_eb_rules_from_plan_fragment():
    pv = terraform_plan.load(FIX / "plan_azure_eb_fragment.json")
    by = {r.address: r for r in pv.retiring}
    legacy = providers.view("azurerm_linux_web_app", by["azurerm_linux_web_app.legacy"].attributes, None)
    scoped = providers.view("azurerm_linux_web_app", by["azurerm_linux_web_app.scoped"].attributes, None)
    eb = providers.view("aws_elastic_beanstalk_environment", by["aws_elastic_beanstalk_environment.old"].attributes,
                        "eu-west-1")
    assert legacy.reclaimable.value == Tri.TRUE
    assert scoped.reclaimable.value == Tri.FALSE
    assert eb.reclaimable.value == Tri.TRUE
    assert {e.name for e in eb.endpoints} == {"contoso-old-env.eu-west-1.elasticbeanstalk.com"}
    assert pv.unsupported_deletions == ["aws_instance.worker (aws_instance)"]


# ---------- statistics ----------
@pytest.mark.parametrize("n,t", [(0, 30.0), (1, 27.56), (87, 62.0), (1000, 10.0)])
def test_jeffreys_bounds_match_chi_square_identity(n, t):
    # Gamma(n+1/2, rate T) quantile == chi2(2n+1) quantile / (2T): an independent formula
    mle, lo, hi = rate_bounds(n, t, 0.05)
    assert mle == pytest.approx(n / t)
    assert lo == pytest.approx(chi2.ppf(0.05, 2 * n + 1) / (2 * t), rel=1e-9)
    assert hi == pytest.approx(chi2.ppf(0.95, 2 * n + 1) / (2 * t), rel=1e-9)


def test_quarantine_formula():
    assert quarantine_days(0.5, 0.01) == pytest.approx(math.log(100) / 0.5)
    assert quarantine_days(0.0, 0.01) is None


def _req(day: float, client: str = "198.51.100.7") -> Request:
    return Request(datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day), client, "h", None, "/", 200)


def test_summary_window_and_freshness_flags():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pol = Policy(min_window_days=31, max_staleness_days=2, internal_domains=["corp.example"])
    rows = [_req(1), _req(2, "host.corp.example"), _req(5)]
    s = summarise("x", start, start + timedelta(days=40), rows, start + timedelta(days=41), pol)
    assert s.window_sufficient and s.fresh and s.requests == 3
    assert s.distinct_clients == 2 and s.external_clients == 1
    stale = summarise("x", start, start + timedelta(days=40), rows, start + timedelta(days=45), pol)
    assert not stale.fresh
    short = summarise("x", start, start + timedelta(days=10), rows, start + timedelta(days=10), pol)
    assert not short.window_sufficient


# ---------- five-condition logic ----------
def _res(action="delete"):
    return RetiringResource("aws_s3_bucket.x", "aws_s3_bucket", "aws", action, "x-bkt", "us-east-1", {})


def _ref(kind=RefKind.DNS, removed=False, control=None):
    return Reference("r1", kind, "loc", "text", "x-bkt", removed, control, [])


T, F, U = (ConditionResult(Tri.TRUE, ""), ConditionResult(Tri.FALSE, ""), ConditionResult(Tri.UNKNOWN, ""))


def test_path_status_truth_table():
    c1 = decide.c1_released(_res())
    assert decide.evaluate_path(_ref(), c1, T, T).status == "hijackable"
    assert decide.evaluate_path(_ref(removed=True), c1, T, T).broken_by == ["c3"]
    assert decide.evaluate_path(_ref(), c1, F, T).broken_by == ["c2"]
    assert decide.evaluate_path(_ref(), c1, T, F).broken_by == ["c4"]
    assert decide.evaluate_path(_ref(RefKind.CODE, control="sri"), c1, T, T).broken_by == ["c5"]
    assert decide.evaluate_path(_ref(RefKind.CODE, control="expected_bucket_owner"), c1, T, T).broken_by == ["c5"]
    assert decide.evaluate_path(_ref(), c1, T, U).status == "unknown"
    assert decide.evaluate_path(_ref(RefKind.TRAFFIC), c1, T, T).status == "unknown"   # consumer controls unknown


def test_verdicts():
    strict, bal = Policy(mode="strict"), Policy(mode="balanced")
    c1 = decide.c1_released(_res())
    hij = [decide.evaluate_path(_ref(), c1, T, T)]
    safe = [decide.evaluate_path(_ref(removed=True), c1, T, F)]
    assert decide.verdict(F, hij, T, strict)[0] == Verdict.RELEASE      # non-reclaimable: always release
    assert decide.verdict(U, safe, F, bal)[0] == Verdict.REVIEW
    assert decide.verdict(T, hij, T, bal)[0] == Verdict.BLOCK
    assert decide.verdict(T, safe, F, strict)[0] == Verdict.TOMBSTONE   # strict never releases a reclaimable name
    assert decide.verdict(T, safe, F, bal)[0] == Verdict.RELEASE
    assert decide.verdict(T, [], U, bal)[0] == Verdict.TOMBSTONE        # no logs: consumers not ruled out


def test_c4_requires_fresh_sufficient_quiet_logs():
    assert decide.c4_consumers([]).value == Tri.UNKNOWN
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pol = Policy()
    busy = summarise("busy", start, start + timedelta(days=40), [_req(39.9)], start + timedelta(days=40), pol)
    # 200 requests in the first two days, then 38 silent days: far past the conservative quarantine
    quiet = summarise("quiet", start, start + timedelta(days=40), [_req(i * 0.01) for i in range(200)],
                      start + timedelta(days=40), pol)
    assert decide.c4_consumers([busy]).value == Tri.TRUE
    assert decide.c4_consumers([quiet]).value == Tri.FALSE
