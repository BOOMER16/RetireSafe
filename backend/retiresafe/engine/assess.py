"""Run a full retirement assessment."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import names, redact
from ..analysis.traffic import Policy, summarise
from ..collectors import access_logs, dns_zone, repo_scan, terraform_plan
from ..collectors.dns_zone import DnsRecord
from ..knowledge import providers
from ..knowledge.providers import NAME_BEARING, S3_TYPES
from ..models import (ConditionResult, Evidence, Reference, RefKind, ResourceAssessment, RetiringResource,
                      TrafficSummary, Tri, Verdict)
from . import decide, remediate


@dataclass
class LogInput:
    path: str
    format: str                       # clf | s3 | cloudfront
    host: str | None = None           # clf only: the hostname this server log belongs to
    covers: list[str] = field(default_factory=list)   # extra names (bucket / host) this log is known to cover
    path_prefix: str | None = None    # only count requests under this URL path


@dataclass
class AssessmentInput:
    plan: str
    dns: list[tuple[str, str | None]] = field(default_factory=list)   # (path, origin for BIND files)
    repos: dict[str, str] = field(default_factory=dict)               # label -> directory
    logs: list[LogInput] = field(default_factory=list)
    policy: Policy = field(default_factory=Policy)
    as_of: datetime | None = None
    migrate_to: dict[str, str] = field(default_factory=dict)


@dataclass
class AssessmentResult:
    as_of: datetime
    plan: terraform_plan.PlanView
    resources: list[ResourceAssessment]
    evidence: list[Evidence]
    inputs: list[dict]
    parse_stats: dict[str, dict]
    scan_stats: dict[str, dict]
    not_checked: list[str]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_record(role: str, path: Path) -> dict:
    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file() and ".git" not in p.parts)
        h = hashlib.sha256()
        for p in files:
            h.update(p.relative_to(path).as_posix().encode())
            h.update(sha256(p).encode())
        return {"role": role, "name": path.name, "sha256_tree": h.hexdigest(), "files": len(files)}
    return {"role": role, "name": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}


def _dns_matches(res: RetiringResource, records: list[DnsRecord]) -> list[tuple[DnsRecord, str]]:
    """Records pointing at the resource, directly or through a chain of records in the inventory."""
    endpoints = {e.name.lower() for e in res.endpoints}
    is_s3 = res.type in S3_TYPES
    matched: dict[int, tuple[DnsRecord, str]] = {}
    for i, r in enumerate(records):
        if r.type not in ("CNAME", "A", "AAAA") and not r.alias_target:
            continue
        for v in r.values:
            if v in endpoints or (is_s3 and names.bucket_from_dns(r.name, v) == (res.name or "").lower()):
                matched[i] = (r, v)
    changed = True
    while changed:                      # follow CNAME chains inside the inventory
        changed = False
        hit_names = {m[0].name for m in matched.values()}
        for i, r in enumerate(records):
            if i not in matched and r.type == "CNAME" and any(v in hit_names for v in r.values):
                matched[i] = (r, r.values[0])
                changed = True
    return list(matched.values())


def _iac_hit(values, res: RetiringResource, prefix: str = "") -> tuple[str, str] | None:
    """First attribute (dotted path) whose value references the resource name or one of its endpoints."""
    if isinstance(values, dict):
        items = values.items()
    elif isinstance(values, list):
        items = ((str(i), v) for i, v in enumerate(values))
    else:
        if isinstance(values, str) and res.name:
            v = values
            if v == res.name or res.name in names.s3_buckets_in(v) or any(
                    e.name in v.lower() for e in res.endpoints if e.kind != "s3_bucket"):
                return prefix.lstrip("."), v[:200]
        return None
    for k, v in items:
        hit = _iac_hit(v, res, f"{prefix}.{k}")
        if hit:
            return hit
    return None


def run(inp: AssessmentInput) -> AssessmentResult:
    policy = inp.policy
    as_of = inp.as_of or datetime.now(timezone.utc)
    plan = terraform_plan.load(inp.plan)
    inputs = [_input_record("terraform_plan", Path(inp.plan))]
    evidence = [Evidence("ev:plan", "terraform_plan", f"Terraform {plan.terraform_version} plan, format "
                         f"{plan.format_version}", Path(inp.plan).name)]
    records: list[DnsRecord] = []
    for path, origin in inp.dns:
        records += dns_zone.load_any(path, origin)
        inputs.append(_input_record("dns_inventory", Path(path)))
    for label, d in inp.repos.items():
        inputs.append({**_input_record("repository", Path(d)), "label": label})
    for lg in inp.logs:
        inputs.append({**_input_record(f"access_log:{lg.format}", Path(lg.path)), "host": lg.host})

    plan_dns = {(s.values.get("name", "").rstrip(".").lower(), s.values.get("type"))
                for s in plan.state if s.type == "aws_route53_record" and s.deleted_in_change}
    exported = {(r.name, r.type) for r in records}

    # ---------- references per resource ----------
    per_res: dict[str, dict] = {}
    for res in plan.retiring:
        if res.type not in NAME_BEARING:
            continue
        refs: list[Reference] = []
        dns_by_ref: dict[str, DnsRecord] = {}
        custom_hosts: dict[str, bool] = {}          # hostname -> removed_in_change
        for rec, val in _dns_matches(res, records):
            rid = f"ref:{res.address}:dns:{len(refs)}"
            removed = (rec.name, rec.type) in plan_dns
            ev = f"ev:dns:{rec.location}"
            evidence.append(Evidence(ev, "dns_inventory", f"{rec.name} {rec.type} -> {val}", rec.location))
            refs.append(Reference(rid, RefKind.DNS, rec.location, f"{rec.name} {rec.type} {val}", val, removed,
                                  None, [ev]))
            dns_by_ref[rid] = rec
            custom_hosts[rec.name] = custom_hosts.get(rec.name, True) and removed
        for s in plan.state:                         # infrastructure references in the same state
            if s.address == res.address:
                continue
            if s.type == "aws_route53_record" and (s.values.get("name", "").rstrip(".").lower(),
                                                   s.values.get("type")) in exported:
                continue
            attr = _iac_hit(s.values, res)
            if attr:
                key, val = attr
                if redact.mask_at(s.sensitive, key.split(".")) or redact.SECRET_KEYS.search(key):
                    val = f"[sensitive value; contains a reference to {res.name}]"
                else:
                    val = redact.scrub(val)
                rid = f"ref:{res.address}:iac:{len(refs)}"
                ev = f"ev:iac:{s.address}"
                evidence.append(Evidence(ev, "terraform_plan", f"{s.address}.{key} = {val}", s.address))
                refs.append(Reference(rid, RefKind.IAC, f"{s.address}.{key}", f"{key} = {val}", res.name or "",
                                      s.deleted_in_change, None, [ev]))
        hosts = {e.name for e in res.endpoints if e.kind not in ("s3_bucket", "s3_rest", "s3_website")} | set(custom_hosts)
        buckets = {res.name} if res.type in S3_TYPES and res.name else set()
        per_res[res.address] = {"res": res, "refs": refs, "dns_by_ref": dns_by_ref, "custom": custom_hosts,
                                "hosts": hosts, "buckets": buckets}

    scan_stats = {}
    for label, d in inp.repos.items():
        all_b = set().union(*(v["buckets"] for v in per_res.values())) if per_res else set()
        all_h = set().union(*(v["hosts"] for v in per_res.values())) if per_res else set()
        hits, st = repo_scan.scan(d, all_b, all_h)
        scan_stats[label] = st.__dict__
        for h in hits:
            for v in per_res.values():
                if h.target in v["buckets"] or h.target in v["hosts"]:
                    res = v["res"]
                    rid = f"ref:{res.address}:code:{len(v['refs'])}"
                    loc = f"{label}::{h.file}:{h.line}"
                    ev = f"ev:code:{loc}"
                    evidence.append(Evidence(ev, "repo_scan", h.text, loc, {
                        "integrity_control": h.integrity_control, "method": h.method, "context": h.context}))
                    removed = v["custom"].get(h.target, False)   # custom hostname whose DNS record is removed
                    v["refs"].append(Reference(rid, RefKind.CODE, loc, h.text, h.target, removed,
                                               h.integrity_control, [ev], h.method, h.context))

    # ---------- traffic ----------
    parse_stats: dict[str, dict] = {}
    traffic: dict[str, list[TrafficSummary]] = {a: [] for a in per_res}
    groups: dict[tuple[str, str], list[LogInput]] = {}
    for lg in inp.logs:                               # one parse per file, however many views use it
        groups.setdefault((lg.path, lg.format), []).append(lg)
    for (path, fmt), lgs in groups.items():
        stats = access_logs.ParseStats()
        wmin = wmax = None
        seen_buckets: set[str] = set()
        rows: dict[tuple[int, str], list] = {(i, a): [] for i in range(len(lgs)) for a in per_res}
        targets = {a: v["buckets"] | v["hosts"] | {e.name for e in v["res"].endpoints} for a, v in per_res.items()}
        # for clf logs the host comes from the view (LogInput), not from the line
        view_hosts = [(lg.host or "").lower() if fmt == "clf" else None for lg in lgs]
        view_res = [[a for a in per_res if h and h in targets[a]] if fmt == "clf" else None for h in view_hosts]
        for r in access_logs.read(path, fmt, None, stats):
            wmin = r.ts if wmin is None or r.ts < wmin else wmin
            wmax = r.ts if wmax is None or r.ts > wmax else wmax
            if r.bucket:
                seen_buckets.add(r.bucket)
            for i, lg in enumerate(lgs):
                if lg.path_prefix and not r.path.startswith(lg.path_prefix):
                    continue
                if fmt == "clf":
                    hits = view_res[i]
                else:
                    rhost = r.host.lower() if r.host else None
                    hits = [a for a, v in per_res.items()
                            if (r.bucket and r.bucket in v["buckets"]) or (rhost and rhost in targets[a])]
                for a in hits:
                    rows[(i, a)].append(r)
        parse_stats[Path(path).name] = stats.__dict__
        for i, lg in enumerate(lgs):
            for a, v in per_res.items():
                names_ = targets[a]
                covers = bool(rows[(i, a)]) or bool(set(lg.covers) & names_) or \
                    bool(seen_buckets & v["buckets"]) or (lg.host is not None and lg.host.lower() in names_)
                if not covers:
                    continue
                src = Path(lg.path).name + (f"[{lg.path_prefix}]" if lg.path_prefix else "")
                t = summarise(src, wmin, wmax, rows[(i, a)], as_of, policy)
                evidence.append(Evidence(f"ev:traffic:{src}", "access_log",
                                         f"{t.requests} requests, {t.distinct_clients} clients, window "
                                         f"{t.window_days:.1f} d", Path(lg.path).name))
                traffic[a].append(t)

    # ---------- decisions ----------
    assessments: list[ResourceAssessment] = []
    repo_roots = {k: Path(v) for k, v in inp.repos.items()}
    for res in plan.retiring:
        if res.type not in NAME_BEARING:
            assessments.append(ResourceAssessment(
                res, ConditionResult(Tri.UNKNOWN, "resource type outside pilot coverage"), [], [], [],
                Verdict.NOT_NAME_BEARING, [f"{res.type} is not a name-bearing type in the pilot rule set"], (0.0, 0.0),
                [], [f"takeover rules for {res.type}"]))
            continue
        v = per_res[res.address]
        c2 = providers.view(res.type, plan.raw_before.get(res.address, {}), res.region).reclaimable
        c1 = decide.c1_released(res)
        c4 = decide.c4_consumers(traffic[res.address])
        refs = list(v["refs"])
        if any(t.requests for t in traffic[res.address]):
            rid = f"ref:{res.address}:traffic"
            refs.append(Reference(rid, RefKind.TRAFFIC, "access logs", "requests addressed to the resource",
                                  res.name or "", False, None,
                                  [f"ev:traffic:{t.source}" for t in traffic[res.address]]))
        paths = [decide.evaluate_path(r, c1, c2, c4) for r in refs]
        verd, reasons = decide.verdict(c2, paths, c4, policy)
        not_checked = []
        if not inp.dns:
            not_checked.append("DNS inventory not supplied")
        if not inp.repos:
            not_checked.append("no source repository supplied")
        if not traffic[res.address]:
            not_checked.append("no access logs cover this resource")
        not_checked.append("consumers outside the supplied inventories (third-party sites, offline clients) "
                           "can only be observed through logs")
        a = ResourceAssessment(res, c2, refs, traffic[res.address], paths, verd, reasons,
                               decide.risk_interval(paths, traffic[res.address], policy), [], not_checked)
        a.patches = remediate.build(res, verd, refs, paths, v["dns_by_ref"], repo_roots, policy, inp.migrate_to)
        assessments.append(a)

    global_nc = [f"deleted resource outside pilot coverage: {u}" for u in plan.unsupported_deletions]
    return AssessmentResult(as_of, plan, assessments, evidence, inputs, parse_stats, scan_stats, global_nc)
