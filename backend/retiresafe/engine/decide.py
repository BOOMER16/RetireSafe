"""Five-condition evaluation and verdicts.

A takeover through a reference needs all five conditions:
  c1 resource released, c2 name reassignable, c3 reference survives the change,
  c4 a consumer remains, c5 consumer-side controls permit the replacement.

Path status: any FALSE -> safe; all TRUE -> hijackable; otherwise unknown.

Resource verdict:
  c2 FALSE                         -> RELEASE (nobody else can obtain the name)
  c2 UNKNOWN                       -> REVIEW
  any hijackable path              -> BLOCK
  strict mode                      -> TOMBSTONE (a reclaimable name is never released)
  balanced mode, every path safe and resource-level c4 FALSE -> RELEASE, else TOMBSTONE
"""
from __future__ import annotations

import math

from ..analysis.traffic import Policy, rate_bounds
from ..models import (ConditionResult, PathAssessment, Reference, RefKind, RetiringResource,
                      TrafficSummary, Tri, Verdict)


def c1_released(res: RetiringResource) -> ConditionResult:
    if res.action == "replace":
        return ConditionResult(Tri.TRUE, "replace = delete then create; the name is released between the two steps",
                               ["ev:plan"])
    return ConditionResult(Tri.TRUE, "the plan deletes this resource", ["ev:plan"])


def c4_consumers(traffic: list[TrafficSummary]) -> ConditionResult:
    if not traffic:
        return ConditionResult(Tri.UNKNOWN, "no access logs cover this resource, so remaining consumers cannot be ruled out")
    for t in traffic:
        if t.requests and t.quarantine_days_conservative is not None and t.silence_days is not None \
                and t.silence_days < t.quarantine_days_conservative:
            return ConditionResult(
                Tri.TRUE, f"{t.requests} requests from {t.distinct_clients} clients in {t.source}; silent for "
                f"{t.silence_days:.1f} d, below the conservative quarantine of {t.quarantine_days_conservative:.1f} d",
                [f"ev:traffic:{t.source}"])
    for t in traffic:
        if not t.fresh:
            return ConditionResult(Tri.UNKNOWN, f"{t.source} ends {t.window_end}, too long before the assessment date",
                                   [f"ev:traffic:{t.source}"])
        if not t.window_sufficient:
            return ConditionResult(Tri.UNKNOWN, f"{t.source} covers {t.window_days:.1f} d, shorter than the required "
                                   "window, so periodic clients could be missed", [f"ev:traffic:{t.source}"])
    detail = "; ".join(f"{t.source}: {t.requests} requests, silent {t.silence_days if t.silence_days is not None else t.window_days:.1f} d"
                       for t in traffic)
    return ConditionResult(Tri.FALSE, f"logs are fresh, long enough and quiet past the quarantine ({detail})",
                           [f"ev:traffic:{t.source}" for t in traffic])


def c5_controls(ref: Reference) -> ConditionResult:
    if ref.integrity_control == "sri":
        return ConditionResult(Tri.FALSE, "the referencing tag pins content with Subresource Integrity; a replacement "
                               "file would be refused by the browser", [*ref.evidence_ids, "src:w3c-sri"])
    if ref.integrity_control == "expected_bucket_owner":
        return ConditionResult(Tri.FALSE, "the file passes ExpectedBucketOwner; S3 rejects a bucket owned by another "
                               "account with 403", [*ref.evidence_ids, "src:aws-sdk-s3-expected-owner"])
    if ref.kind == RefKind.TRAFFIC:
        return ConditionResult(Tri.UNKNOWN, "consumers seen only in logs; their integrity checks are unknown",
                               ref.evidence_ids)
    if ref.kind == RefKind.DNS:
        return ConditionResult(Tri.TRUE, "browsers and clients accept whatever the hostname serves", ref.evidence_ids)
    return ConditionResult(Tri.TRUE, "no integrity or owner check detected for this reference", ref.evidence_ids)


def evaluate_path(ref: Reference, c1: ConditionResult, c2: ConditionResult, c4: ConditionResult) -> PathAssessment:
    c3 = (ConditionResult(Tri.FALSE, "the same change removes this reference", ref.evidence_ids)
          if ref.removed_in_change else
          ConditionResult(Tri.TRUE, "the reference is not removed by this change", ref.evidence_ids))
    conds = {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5_controls(ref)}
    broken = [k for k, v in conds.items() if v.value == Tri.FALSE]
    if broken:
        status = "safe"
    elif all(v.value == Tri.TRUE for v in conds.values()):
        status = "hijackable"
    else:
        status = "unknown"
    return PathAssessment(ref.id, conds, status, broken)


def _p(c: ConditionResult, lo_hi: tuple[float, float] | None = None) -> tuple[float, float]:
    if c.value == Tri.FALSE:
        return 0.0, 0.0
    if c.value == Tri.UNKNOWN:
        return 0.0, 1.0
    return lo_hi or (1.0, 1.0)


def consumer_return_interval(traffic: list[TrafficSummary], policy: Policy) -> tuple[float, float] | None:
    """P(at least one request within the policy horizon), from the Jeffreys rate interval of the busiest source."""
    best = None
    for t in traffic:
        if t.requests and t.window_days > 0:
            _, lo, hi = rate_bounds(t.requests, t.window_days, policy.beta)
            iv = (1 - math.exp(-lo * policy.horizon_days), 1 - math.exp(-min(hi, 1e6) * policy.horizon_days))
            best = iv if best is None or iv[1] > best[1] else best
    return best


def risk_interval(paths: list[PathAssessment], traffic: list[TrafficSummary], policy: Policy) -> tuple[float, float]:
    ret = consumer_return_interval(traffic, policy)
    lo_max = hi_max = 0.0
    for p in paths:
        lo, hi = 1.0, 1.0
        for k, c in p.conditions.items():
            a, b = _p(c, ret if k == "c4" else None)
            lo, hi = lo * a, hi * b
        lo_max, hi_max = max(lo_max, lo), max(hi_max, hi)
    return round(lo_max, 6), round(hi_max, 6)


def verdict(c2: ConditionResult, paths: list[PathAssessment], c4: ConditionResult,
            policy: Policy) -> tuple[Verdict, list[str]]:
    hijackable = [p for p in paths if p.status == "hijackable"]
    unknown = [p for p in paths if p.status == "unknown"]
    if c2.value == Tri.FALSE:
        return Verdict.RELEASE, ["the name cannot be obtained by another party (" + c2.reason + ")"]
    if c2.value == Tri.UNKNOWN:
        return Verdict.REVIEW, ["cannot tell whether the released name is reclaimable: " + c2.reason]
    if hijackable:
        return Verdict.BLOCK, [f"{len(hijackable)} surviving reference(s) would hand traffic to whoever reclaims "
                               "the name; remove or migrate them before deleting"]
    if policy.mode == "strict":
        return Verdict.TOMBSTONE, ["strict policy: a reclaimable name is never released; delete the contents and "
                                   "keep owning the name"]
    reasons = []
    if unknown:
        reasons.append(f"{len(unknown)} reference path(s) could not be fully evaluated")
    if c4.value != Tri.FALSE:
        reasons.append("consumers not ruled out: " + c4.reason)
    if reasons:
        return Verdict.TOMBSTONE, reasons
    return Verdict.RELEASE, ["no surviving reference is hijackable and the logs show no remaining consumers"]
