"""SPF delegation walk (stubbed DNS) and live checks (network tests run in CI)."""
import os

import pytest

from retiresafe.probes import email_domains as ed
from retiresafe.probes import live

NETWORK = pytest.mark.skipif(os.environ.get("RETIRESAFE_NETWORK_TESTS") != "1",
                             reason="set RETIRESAFE_NETWORK_TESTS=1 (CI does) for live DNS/RDAP tests")


def _stub(monkeypatch, zone: dict):
    def q(res, name, rtype, retries=2):
        return zone.get((name, rtype), ("NXDOMAIN", []))
    monkeypatch.setattr(live, "query", q)


def test_spf_dangling_include(monkeypatch):
    _stub(monkeypatch, {
        ("corp.example", "TXT"): ("OK", ['"v=spf1 include:_spf.mailer.example include:old-promo-2009.com -all"']),
        ("_spf.mailer.example", "TXT"): ("OK", ['"v=spf1 ip4:192.0.2.0/24 -all"']),
        ("mailer.example", "NS"): ("OK", ["ns1.mailer.example."]),
        # old-promo-2009.com: NS -> NXDOMAIN (default): the registrable domain does not exist
    })
    f = ed.check_spf("corp.example")
    assert f.unregistered == ["old-promo-2009.com"] and f.classification == "spf_delegates_to_unregistered_domain"
    assert f.lookups == 2


def test_spf_missing_record_macro_and_limit(monkeypatch):
    terms = " ".join(f"include:s{i}.mailer.example" for i in range(11))
    zone = {("corp.example", "TXT"): ("OK", [f'"v=spf1 {terms} exists:%{{i}}.rbl.example -all"']),
            ("mailer.example", "NS"): ("OK", ["ns1."])}
    for i in range(11):
        zone[(f"s{i}.mailer.example", "TXT")] = ("OK", ['"v=spf1 -all"'])
    _stub(monkeypatch, zone)
    f = ed.check_spf("corp.example")
    assert f.lookups == 12 and f.classification == "spf_lookup_limit_exceeded"   # RFC 7208 limit is 10
    assert not any("%{" in d for d in f.delegations)                            # macros skipped
    zone[("s3.mailer.example", "TXT")] = ("NOANSWER", [])
    f = ed.check_spf("corp.example")
    assert "s3.mailer.example" in f.missing_spf


def test_spf_timeout_is_an_error_not_ok(monkeypatch):
    _stub(monkeypatch, {("corp.example", "TXT"): ("TIMEOUT", [])})
    assert ed.check_spf("corp.example").classification == "lookup_error"


@NETWORK
def test_live_spf_public_domain():
    f = ed.check_spf("gmail.com")
    assert f.classification == "ok" and f.delegations


@NETWORK
def test_live_rdap_expiry():
    r = ed.domain_expiry("example.com")
    assert r["status"] == "registered" and r["expires"]
