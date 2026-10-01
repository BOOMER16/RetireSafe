"""Collectors against real inputs: AWS-published log examples, NASA traffic, real Terraform output."""
from datetime import datetime, timezone

from conftest import FIX, GEN, PILOT
from retiresafe.collectors import access_logs, dns_zone, repo_scan, terraform_plan
from retiresafe.collectors.access_logs import ParseStats, _clf_time


# ---------- access logs ----------
def test_s3_server_access_log_doc_examples():
    st = ParseStats()
    rows = list(access_logs.read(FIX / "aws_s3_access_log_doc_examples.log", "s3", None, st))
    assert (st.lines, st.parsed, st.failed) == (5, 5, 0)
    r = rows[0]   # values read off the AWS example record
    assert r.bucket == "awsexamplebucket1"
    assert r.client == "192.0.2.3"
    assert r.ts == datetime(2019, 2, 6, 0, 0, 38, tzinfo=timezone.utc)
    assert r.status == 200
    assert r.host == "awsexamplebucket1.s3.us-west-1.amazonaws.com"
    assert r.path == "/awsexamplebucket1"
    assert rows[2].status == 404          # REST.GET.BUCKETPOLICY -> NoSuchBucketPolicy


def test_cloudfront_doc_examples():
    st = ParseStats()
    rows = list(access_logs.read(FIX / "aws_cloudfront_doc_examples.log", "cloudfront", None, st))
    assert (st.lines, st.parsed, st.failed) == (4, 4, 0)
    assert rows[0].ts == datetime(2019, 12, 4, 21, 2, 31, tzinfo=timezone.utc)
    assert rows[0].client == "192.0.2.100" and rows[0].path == "/index.html" and rows[0].status == 200
    assert rows[0].host == "d111111abcdef8.cloudfront.net"
    assert rows[3].host == "www.example.com" and rows[3].status == 502   # x-host-header wins over cs(Host)


def test_nasa_clf_sample_and_fast_time_parser():
    st = ParseStats()
    rows = list(access_logs.read(FIX / "nasa_jul95_first2000.log", "clf", "www.nasa.example", st))
    assert st.lines == 2000 and st.parsed + st.failed == 2000
    assert rows[0].client == "199.72.81.55" and rows[0].path == "/history/apollo/"
    assert rows[0].ts == datetime(1995, 7, 1, 4, 0, 1, tzinfo=timezone.utc)   # -0400 converted to UTC
    for ln in (FIX / "nasa_jul95_first2000.log").read_text(encoding="latin-1").splitlines():
        ts = ln.split("[", 1)[1].split("]", 1)[0]
        assert _clf_time(ts) == datetime.strptime(ts, "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)


# ---------- Terraform plan (real terraform 1.16.4 + hashicorp/aws 6.67.0 output) ----------
def test_plan_before_retiring_resources():
    pv = terraform_plan.load(GEN / "plan_before.json")
    assert pv.terraform_version == "1.16.4"
    by = {r.address: r for r in pv.retiring}
    assert set(by) == {"aws_s3_bucket.archive", "aws_s3_bucket.event_assets", "aws_s3_bucket.event_site",
                       "aws_s3_bucket.legacy_downloads", "aws_s3_bucket_website_configuration.event_site"}
    assert by["aws_s3_bucket.event_assets"].name == "rs-pilot-event-assets-2025"
    assert by["aws_s3_bucket.event_site"].region == "us-east-1"
    eps = {e.name for e in by["aws_s3_bucket.event_site"].endpoints}
    assert "event.retiresafe-pilot.example.s3-website-us-east-1.amazonaws.com" in eps
    assert pv.unsupported_deletions == ["aws_s3_bucket_website_configuration.event_site "
                                        "(aws_s3_bucket_website_configuration)"]
    assert any(s.address == "aws_ssm_parameter.assets_base_url" and not s.deleted_in_change for s in pv.state)


def test_plan_after_only_archive_is_name_bearing_deletion():
    pv = terraform_plan.load(GEN / "plan_after.json")
    assert [r.address for r in pv.retiring if r.type == "aws_s3_bucket"] == ["aws_s3_bucket.archive"]


# ---------- DNS ----------
def test_route53_and_bind_exports_agree():
    r53 = dns_zone.load_route53(GEN / "route53_before.json")
    bind = dns_zone.load_bind(GEN / "zone_before.db")
    pick = lambda recs: {(r.name, r.type, tuple(sorted(r.values))) for r in recs if r.type in ("CNAME", "A")}
    assert pick(r53) == pick(bind)
    cn = {r.name: r.values[0] for r in r53 if r.type == "CNAME"}
    assert cn == {"cdn.retiresafe-pilot.example": "rs-pilot-event-assets-2025.s3.amazonaws.com",
                  "event.retiresafe-pilot.example": "event.retiresafe-pilot.example.s3-website-us-east-1.amazonaws.com"}


def test_route53_after_has_references_removed():
    names = {r.name for r in dns_zone.load_route53(GEN / "route53_after.json") if r.type == "CNAME"}
    assert names == set()


# ---------- repository scan ----------
def test_repo_scan_finds_every_reference_style_and_control():
    hits, st = repo_scan.scan(PILOT / "app", {"rs-pilot-event-assets-2025", "rs-pilot-legacy-downloads"},
                              {"event.retiresafe-pilot.example"})
    got = {(h.file, h.line, h.target, h.integrity_control) for h in hits}
    assert ("index.html", 7, "rs-pilot-event-assets-2025", "sri") in got                    # SRI-pinned stylesheet
    assert ("index.html", 14, "rs-pilot-event-assets-2025", None) in got                    # unpinned script
    assert ("index.html", 12, "event.retiresafe-pilot.example", None) in got                # custom-domain link
    assert ("tools/upload_assets.py", 10, "rs-pilot-event-assets-2025", "expected_bucket_owner") in got
    assert ("tools/sync_downloads.py", 8, "rs-pilot-legacy-downloads", None) in got         # Bucket= kwarg
    assert ("tools/sync_downloads.py", 9, "rs-pilot-legacy-downloads", None) in got         # positional literal
    assert st.files_scanned >= 5
