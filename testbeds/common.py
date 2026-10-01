"""Shared helpers for RetireSafe test beds (passive, read-only checks only)."""
import json
import os
import dns.resolver
import dns.exception
import tldextract

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("RS_DATA", os.path.join(ROOT, "data"))
OUT = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUT, exist_ok=True)

_ext = tldextract.TLDExtract(suffix_list_urls=())  # bundled PSL snapshot, no network


def registrable(name):
    r = _ext(name.rstrip("."))
    return getattr(r, "top_domain_under_public_suffix", None) or r.registered_domain


def resolver():
    r = dns.resolver.Resolver()
    r.lifetime = 6
    r.timeout = 3
    return r


def query(res, name, rtype, tcp=False):
    """Return (status, answers). status in OK, NXDOMAIN, NOANSWER, TIMEOUT, ERROR."""
    try:
        a = res.resolve(name, rtype, tcp=tcp, raise_on_no_answer=False)
        if a.rrset is None:
            return "NOANSWER", []
        return "OK", [x.to_text() for x in a]
    except dns.resolver.NXDOMAIN:
        return "NXDOMAIN", []
    except (dns.exception.Timeout, dns.resolver.LifetimeTimeout):
        return "TIMEOUT", []
    except dns.resolver.NoNameservers:
        return "SERVFAIL", []
    except Exception as e:  # noqa
        return "ERROR", [type(e).__name__]


def save(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=2, default=str)
