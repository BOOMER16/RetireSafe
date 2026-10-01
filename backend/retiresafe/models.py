"""Core data model for RetireSafe assessments.

Every judgement in an assessment is a ``Finding`` that carries the evidence it
was derived from. Condition values are three-valued (TRUE / FALSE / UNKNOWN) so
that missing evidence is never silently treated as "safe".
"""
from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from typing import Any


class Tri(str, enum.Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class Verdict(str, enum.Enum):
    RELEASE = "release"        # deleting and releasing the name is safe on the evidence
    BLOCK = "block"            # a surviving reference is hijackable now; fix before deleting
    TOMBSTONE = "tombstone"    # delete contents but keep owning the name
    REVIEW = "review"          # cannot be classified; a human must decide
    NOT_NAME_BEARING = "not_name_bearing"  # resource type has no reclaimable public name


class RefKind(str, enum.Enum):
    DNS = "dns"
    CODE = "code"
    IAC = "iac"
    TRAFFIC = "traffic"        # consumers seen in logs, reference location unknown


@dataclass
class Evidence:
    id: str
    source: str                # e.g. "terraform_plan", "route53_export", "repo_scan", "s3_probe"
    detail: str
    location: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Endpoint:
    """A public name through which a resource is reachable."""
    name: str                  # hostname, or bucket name for S3 API style access
    kind: str                  # "s3_bucket", "s3_website", "azure_app", "eb_cname", ...


@dataclass
class RetiringResource:
    address: str               # Terraform address, e.g. aws_s3_bucket.event_assets
    type: str
    provider: str
    action: str                # "delete" or "replace"
    name: str | None           # the reclaimable name (bucket name, app name, CNAME prefix)
    region: str | None
    attributes: dict[str, Any]
    endpoints: list[Endpoint] = field(default_factory=list)


@dataclass
class Reference:
    id: str
    kind: RefKind
    location: str              # file:line, zone record, terraform address, log source
    text: str                  # the matched text or record value
    target_name: str           # endpoint / bucket name it points at
    removed_in_change: bool = False
    integrity_control: str | None = None   # e.g. "sri", "expected_bucket_owner"
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class TrafficSummary:
    source: str
    window_start: str | None
    window_end: str | None
    window_days: float
    requests: int
    last_seen: str | None
    silence_days: float | None
    rate_mle_per_day: float | None
    rate_lower_per_day: float | None
    quarantine_days_mle: float | None
    quarantine_days_conservative: float | None
    distinct_clients: int
    distinct_networks_24: int
    external_clients: int
    external_share: float | None
    fresh: bool
    window_sufficient: bool


@dataclass
class ConditionResult:
    value: Tri
    reason: str
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class PathAssessment:
    reference_id: str
    conditions: dict[str, ConditionResult]   # keys c1..c5
    status: str                               # "safe", "hijackable", "unknown"
    broken_by: list[str]                      # which conditions are FALSE


@dataclass
class Patch:
    kind: str                  # "route53_change_batch", "terraform_hcl", "code_diff", "advice"
    title: str
    content: str
    applies_to: list[str] = field(default_factory=list)
    operation: dict | None = None   # machine-applicable form (the content is for people and may be redacted)


@dataclass
class ResourceAssessment:
    resource: RetiringResource
    reclaimable: ConditionResult              # condition 2 at resource level
    references: list[Reference]
    traffic: list[TrafficSummary]
    paths: list[PathAssessment]
    verdict: Verdict
    reasons: list[str]
    risk_interval: tuple[float, float]
    patches: list[Patch] = field(default_factory=list)
    not_checked: list[str] = field(default_factory=list)


def to_dict(obj: Any) -> Any:
    """Dataclass -> JSON-safe dict (enums become their values)."""
    def conv(x: Any) -> Any:
        if isinstance(x, enum.Enum):
            return x.value
        if isinstance(x, dict):
            return {k: conv(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [conv(v) for v in x]
        return x
    return conv(asdict(obj) if hasattr(obj, "__dataclass_fields__") else obj)
