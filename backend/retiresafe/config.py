"""Turn plain dict / JSON configuration into engine inputs (shared by CLI and API)."""
from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime

from .analysis.traffic import Policy
from .engine.assess import LogInput

POLICY_FIELDS = {f.name for f in fields(Policy)}
LOG_FORMATS = {"clf", "s3", "cloudfront"}


def policy_from(d: dict | None) -> Policy:
    d = dict(d or {})
    unknown = set(d) - POLICY_FIELDS
    if unknown:
        raise ValueError(f"unknown policy fields: {sorted(unknown)}")
    p = Policy(**d)
    if not 0 < p.alpha < 1 or not 0 < p.beta < 0.5:
        raise ValueError("policy.alpha must be in (0,1) and policy.beta in (0,0.5)")
    if p.mode not in ("strict", "balanced"):
        raise ValueError("policy.mode must be 'strict' or 'balanced'")
    if p.min_window_days <= 0 or p.max_staleness_days < 0:
        raise ValueError("policy windows must be positive")
    return p


def log_from(d: dict, path: str) -> LogInput:
    fmt = d.get("format")
    if fmt not in LOG_FORMATS:
        raise ValueError(f"log {path}: format must be one of {sorted(LOG_FORMATS)}")
    if fmt == "clf" and not d.get("host"):
        raise ValueError(f"log {path}: clf logs need 'host' (the hostname the server log belongs to)")
    return LogInput(path, fmt, d.get("host"), list(d.get("covers", [])), d.get("path_prefix"))


def parse_as_of(s: str | None) -> datetime | None:
    if not s:
        return None
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("as_of must include a timezone, e.g. 2026-10-01T00:00:00Z")
    return t


def policy_dict(p: Policy) -> dict:
    return asdict(p)
