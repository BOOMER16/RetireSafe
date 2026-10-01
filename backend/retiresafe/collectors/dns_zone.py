"""DNS inventory readers: Route 53 exports and BIND zone files.

Route 53: the JSON printed by
``aws route53 list-resource-record-sets --hosted-zone-id <id>`` (a dict with
``ResourceRecordSets``) or a bare list of record sets.
BIND: a standard master/zone file, parsed with dnspython.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import dns.rdatatype
import dns.zone


@dataclass
class DnsRecord:
    name: str                       # fully qualified, no trailing dot, lower case
    type: str
    values: list[str]               # targets / rdata text (no trailing dots for host targets)
    ttl: int | None
    source: str                     # file name
    location: str                   # human-readable locator
    alias_target: str | None = None
    raw: dict = field(default_factory=dict)   # original record set (Route 53) for exact patches


def _host(s: str) -> str:
    return s.strip().rstrip(".").lower()


def load_route53(path: str | Path) -> list[DnsRecord]:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    sets = data.get("ResourceRecordSets", data) if isinstance(data, dict) else data
    out = []
    for i, rs in enumerate(sets):
        rtype = rs["Type"]
        name = _host(rs["Name"].replace("\\052", "*"))
        alias = rs.get("AliasTarget", {}).get("DNSName")
        values = [_host(alias)] if alias else [
            (_host(v["Value"]) if rtype in ("CNAME", "NS", "PTR") else v["Value"])
            for v in rs.get("ResourceRecords", [])]
        out.append(DnsRecord(name, rtype, values, rs.get("TTL"), path.name,
                             f"{path.name}#ResourceRecordSets[{i}] {name} {rtype}",
                             _host(alias) if alias else None, rs))
    return out


SOA_OWNER = re.compile(r"^(\S+)\s+(?:\d+\s+)?(?:IN\s+)?(?:\d+\s+)?SOA\b", re.M | re.I)


def load_bind(path: str | Path, origin: str | None = None) -> list[DnsRecord]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if origin is None and "$ORIGIN" not in text.upper():
        m = SOA_OWNER.search(text)           # no $ORIGIN: the SOA owner is the zone apex
        if m and m.group(1).endswith("."):
            origin = m.group(1)
    z = dns.zone.from_text(text, origin=origin, relativize=False, check_origin=False)
    out = []
    for name, node in z.nodes.items():
        fq = _host(name.to_text())
        for rds in node.rdatasets:
            rtype = dns.rdatatype.to_text(rds.rdtype)
            if rtype in ("CNAME", "NS", "PTR"):
                values = [_host(r.target.to_text()) for r in rds]
            elif rtype == "MX":
                values = [_host(r.exchange.to_text()) for r in rds]
            else:
                values = [r.to_text() for r in rds]
            out.append(DnsRecord(fq, rtype, values, rds.ttl, path.name, f"{path.name} {fq} {rtype}"))
    return out


def load_any(path: str | Path, origin: str | None = None) -> list[DnsRecord]:
    p = Path(path)
    text = p.read_text(encoding="utf-8").lstrip()
    if text.startswith("{") or text.startswith("["):
        return load_route53(p)
    return load_bind(p, origin)
