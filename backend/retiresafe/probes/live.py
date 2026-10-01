"""Live, read-only probes: DNS CNAME-chain walk and S3 bucket existence.

These are the TB1 research checks, packaged for drift monitoring: they find
references that were left dangling by deletions made outside the gate.
Only scan names your organisation owns.
"""
from __future__ import annotations

import concurrent.futures as cf
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import dns.exception
import dns.resolver
import requests
import tldextract

from .. import names
from ..knowledge import fingerprints

_ext = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)  # bundled list, no disk cache


def registrable(host: str) -> str | None:
    r = _ext(host.rstrip("."))
    if hasattr(r, "top_domain_under_public_suffix"):
        return r.top_domain_under_public_suffix or None
    return r.registered_domain or None


def _resolver() -> dns.resolver.Resolver:
    r = dns.resolver.Resolver()
    r.lifetime, r.timeout = 6, 3
    r.use_edns(0, 0, 4096)          # large TXT/SPF answers without needing TCP
    return r


RETRYABLE = ("TIMEOUT", "SERVFAIL", "ERROR")


def query(res: dns.resolver.Resolver, name: str, rtype: str, retries: int = 2) -> tuple[str, list[str]]:
    """Resolve with retries; transient failures are retried, never reported as an answer."""
    for attempt in range(retries + 1):
        st, ans = _query_once(res, name, rtype)
        if st not in RETRYABLE:
            return st, ans
        time.sleep(0.5 * (2 ** attempt))
    return st, ans


def _query_once(res: dns.resolver.Resolver, name: str, rtype: str) -> tuple[str, list[str]]:
    try:
        a = res.resolve(name, rtype, raise_on_no_answer=False)
        return ("NOANSWER", []) if a.rrset is None else ("OK", [x.to_text() for x in a])
    except dns.resolver.NXDOMAIN:
        return "NXDOMAIN", []
    except (dns.exception.Timeout, dns.resolver.LifetimeTimeout):
        return "TIMEOUT", []
    except dns.resolver.NoNameservers:
        return "SERVFAIL", []
    except Exception as e:  # noqa: BLE001
        return "ERROR", [type(e).__name__]


def s3_bucket_state(bucket: str, session: requests.Session | None = None) -> str:
    """'missing' (404 NoSuchBucket), 'exists:<status>', or 'error'. Read-only GET, no credentials."""
    s = session or requests
    try:
        r = s.get(f"https://s3.amazonaws.com/{bucket}", timeout=10, allow_redirects=False)
    except requests.RequestException:
        return "error"
    if r.status_code == 404 and "NoSuchBucket" in r.text:
        return "missing"
    return f"exists:{r.status_code}"


@dataclass
class DriftFinding:
    hostname: str
    chain: list[str]
    service: str | None
    target_status: str | None
    classification: str          # see LADDER
    detail: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


LADDER = ["no_cname", "cname_resolves", "provider_needs_http_check", "stale_target_missing",
          "reclaimable_candidate", "dangling_unregistered_domain", "lookup_error"]


def check_hostname(host: str) -> DriftFinding:
    res = _resolver()
    chain, cur, fp = [], host.rstrip(".").lower(), None
    for _ in range(8):
        st, ans = query(res, cur, "CNAME")
        if st in RETRYABLE:          # never mistake an unanswered lookup for "no CNAME"
            return DriftFinding(host, chain, fp["service"] if fp else None, st, "lookup_error",
                                f"CNAME lookup for {cur} failed ({st}) after retries")
        if st != "OK" or not ans:
            break
        cur = ans[0].rstrip(".").lower()
        chain.append(cur)
        fp = fp or fingerprints.match(cur)
    if not chain:
        st, _ = query(res, host, "A")
        cls = "lookup_error" if st in RETRYABLE else "no_cname"
        return DriftFinding(host, [], None, st, cls, f"no CNAME (A lookup: {st})")
    st, _ = query(res, chain[-1], "A")
    if st == "NXDOMAIN" and query(res, chain[-1], "AAAA")[0] != "NXDOMAIN":
        st = "NOANSWER"
    if st in RETRYABLE:
        return DriftFinding(host, chain, fp["service"] if fp else None, st, "lookup_error",
                            f"address lookup for {chain[-1]} failed ({st}) after retries")
    service = fp["service"] if fp else None
    if st == "NXDOMAIN":
        reg = registrable(chain[-1])
        if reg and query(res, reg, "NS")[0] == "NXDOMAIN":
            return DriftFinding(host, chain, service, st, "dangling_unregistered_domain",
                                f"target's registrable domain {reg} does not exist; anyone may register it")
    if service == "AWS/S3":
        # the S3 hop of the chain; a bare endpoint means S3 uses the requested hostname as the bucket
        s3_hop = next(h for h in reversed(chain) if fingerprints.S3_HOST.search(h))
        bucket = names.bucket_from_dns(host, s3_hop)
        state = s3_bucket_state(bucket) if bucket else "error"
        if state == "missing":
            return DriftFinding(host, chain, service, st, "reclaimable_candidate",
                                f"bucket {bucket!r} does not exist (NoSuchBucket); in the global namespace any "
                                "account can create it")
        return DriftFinding(host, chain, service, st, "cname_resolves", f"bucket {bucket!r} {state}")
    if fp and st == "NXDOMAIN" and fp.get("nxdomain") and fp.get("vulnerable"):
        return DriftFinding(host, chain, service, st, "reclaimable_candidate",
                            f"{service} target does not exist and the catalogue lists NXDOMAIN takeover as possible")
    if st == "NXDOMAIN":
        return DriftFinding(host, chain, service, st, "stale_target_missing", "CNAME target does not exist")
    if fp and fp.get("vulnerable") and not fp.get("nxdomain"):
        return DriftFinding(host, chain, service, st, "provider_needs_http_check",
                            f"{service} is takeover-prone via HTTP fingerprint {fp.get('fingerprint')!r}; "
                            "not confirmed by this DNS-only check")
    return DriftFinding(host, chain, service, st, "cname_resolves", "chain resolves")


def scan(hostnames: list[str], workers: int = 16) -> list[DriftFinding]:
    hosts = list(dict.fromkeys(h.strip().rstrip(".").lower() for h in hostnames if h.strip()))
    with cf.ThreadPoolExecutor(workers) as ex:
        return list(ex.map(check_hostname, hosts))
