"""Email-trust and registration checks for domains you own (SubdoMailing class, Guardio 2024).

* SPF: walk ``v=spf1`` records (RFC 7208) through ``include:`` and ``redirect=``, collect every
  domain the policy delegates to, and flag delegations to domains that are not registered. Anyone
  can register such a domain and publish an SPF record that authorises their own mail servers to
  send as you. Also reports the RFC 7208 limit of 10 DNS-querying terms.
* Expiry: look up a domain's registration expiry through RDAP (RFC 9082/9083) using IANA's
  bootstrap file (RFC 9224), so a domain that RetireSafe users depend on is renewed in time.

Read-only DNS/HTTPS lookups; only run them for domains you own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from . import live

LOOKUP_TERMS = re.compile(r"^(?:[+\-~?])?(include|a|mx|ptr|exists)(?::|$)|^redirect=", re.I)
DOMAIN_ARG = re.compile(r"^(?:[+\-~?])?(include|a|mx|ptr|exists):([^/\s]+)|^redirect=(\S+)", re.I)


@dataclass
class SpfFinding:
    domain: str
    lookups: int
    delegations: list[str] = field(default_factory=list)
    unregistered: list[str] = field(default_factory=list)     # registrable domain does not exist
    missing_spf: list[str] = field(default_factory=list)      # included name has no SPF record
    errors: list[str] = field(default_factory=list)

    @property
    def classification(self) -> str:
        if self.unregistered:
            return "spf_delegates_to_unregistered_domain"
        if self.errors:
            return "lookup_error"
        if self.lookups > 10:
            return "spf_lookup_limit_exceeded"
        if self.missing_spf:
            return "spf_include_without_record"
        return "ok"


def spf_records(res, domain: str) -> tuple[str, list[str]]:
    st, ans = live.query(res, domain, "TXT")
    if st != "OK":
        return st, []
    recs = []
    for a in ans:
        txt = "".join(p.strip('"') for p in re.findall(r'"((?:[^"\\]|\\.)*)"', a)) or a.strip('"')
        if txt.lower().startswith("v=spf1"):
            recs.append(txt)
    return "OK", recs


def check_spf(domain: str, max_depth: int = 10) -> SpfFinding:
    res = live._resolver()
    out = SpfFinding(domain.lower().strip("."), 0)
    seen: set[str] = set()

    def walk(d: str, depth: int) -> None:
        if d in seen or depth > max_depth:
            return
        seen.add(d)
        st, recs = spf_records(res, d)
        if st in live.RETRYABLE:
            out.errors.append(f"TXT {d}: {st}")
            return
        if not recs:
            if d != out.domain:
                out.missing_spf.append(d)
            return
        for term in recs[0].split()[1:]:
            if LOOKUP_TERMS.match(term):
                out.lookups += 1
            m = DOMAIN_ARG.match(term)
            if not m:
                continue
            kind = (m.group(1) or "redirect").lower()
            target = (m.group(2) or m.group(3) or "").lower().strip(".")
            if not target or "%{" in target:          # macros are evaluated per message; skip
                continue
            out.delegations.append(f"{kind}:{target}")
            reg = live.registrable(target)
            if reg and live.query(res, reg, "NS")[0] == "NXDOMAIN":
                out.unregistered.append(reg)
            elif kind in ("include", "redirect"):
                walk(target, depth + 1)

    walk(out.domain, 0)
    out.unregistered = sorted(set(out.unregistered))
    return out


# ---------------- RDAP expiry ----------------
IANA_BOOTSTRAP = "https://data.iana.org/rdap/dns.json"


def rdap_base(tld: str, session: requests.Session) -> str | None:
    data = session.get(IANA_BOOTSTRAP, timeout=20).json()
    for tlds, urls in data.get("services", []):
        if tld.lower() in tlds and urls:
            return next((u for u in urls if u.startswith("https://")), urls[0])
    return None


def domain_expiry(domain: str, session: requests.Session | None = None) -> dict:
    s = session or requests.Session()
    reg = live.registrable(domain) or domain
    base = rdap_base(reg.rsplit(".", 1)[-1], s)
    if not base:
        return {"domain": reg, "status": "no_rdap_service"}
    r = s.get(base.rstrip("/") + "/domain/" + reg, timeout=20, headers={"Accept": "application/rdap+json"})
    if r.status_code == 404:
        return {"domain": reg, "status": "not_registered"}
    r.raise_for_status()
    events = {e.get("eventAction"): e.get("eventDate") for e in r.json().get("events", [])}
    exp = events.get("expiration")
    days = None
    if exp:
        days = (datetime.fromisoformat(exp.replace("Z", "+00:00")) - datetime.now(timezone.utc)).days
    return {"domain": reg, "status": "registered", "expires": exp, "days_left": days, "rdap": base}
