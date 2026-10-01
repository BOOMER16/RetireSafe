"""Time-limited, attributable exceptions to the gate.

A waiver file (JSON)::

    {"waivers": [
      {"resource": "aws_s3_bucket.event_assets",
       "kind": "accept_reference",            # accept the risk of matching reference paths
       "reference": "app::docs/*",            # optional glob over reference locations
       "reason": "docs archive is frozen; link removed in next release",
       "approved_by": "security@corp.example",
       "expires": "2026-11-30"},
      {"resource": "aws_s3_bucket.legacy_downloads",
       "kind": "allow_release",               # strict mode only: release a reclaimable name
       "reason": "...", "approved_by": "...", "expires": "2026-10-15"}]}

Rules: every waiver needs a reason, an approver and an expiry no further than
``policy.max_waiver_days`` ahead; expired or malformed waivers are ignored and reported.
``allow_release`` never releases a resource that still has unwaived hijackable paths.
"""
from __future__ import annotations

import fnmatch
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

KINDS = {"accept_reference", "allow_release"}


@dataclass
class Waiver:
    resource: str
    kind: str
    reason: str
    approved_by: str
    expires: str
    reference: str | None = None

    def matches_ref(self, location: str) -> bool:
        return self.reference is None or fnmatch.fnmatch(location, self.reference)


def load(path: str | Path | None = None, inline: list[dict] | None = None, as_of: datetime | None = None,
         max_days: int = 90) -> tuple[list[Waiver], list[dict]]:
    raw = list(inline or [])
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        raw += data.get("waivers", []) if isinstance(data, dict) else data
    today = (as_of or datetime.now()).date()
    ok, rejected = [], []
    for w in raw:
        problem = None
        if w.get("kind") not in KINDS:
            problem = f"kind must be one of {sorted(KINDS)}"
        elif not all(str(w.get(k, "")).strip() for k in ("resource", "reason", "approved_by", "expires")):
            problem = "resource, reason, approved_by and expires are required"
        else:
            try:
                exp = date.fromisoformat(w["expires"])
            except ValueError:
                exp, problem = None, "expires must be an ISO date (YYYY-MM-DD)"
            if exp and exp < today:
                problem = f"expired on {exp}"
            elif exp and (exp - today).days > max_days:
                problem = f"expiry more than {max_days} days ahead; renew instead"
        if problem:
            rejected.append({"waiver": w, "problem": problem})
        else:
            ok.append(Waiver(w["resource"], w["kind"], w["reason"], w["approved_by"], w["expires"],
                             w.get("reference")))
    return ok, rejected


def as_dict(w: Waiver) -> dict:
    return asdict(w)
