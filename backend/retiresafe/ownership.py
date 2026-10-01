"""Scope guard: live probes may only touch names the operator declares as their own."""
from __future__ import annotations

import os


def owned_domains(extra: list[str] | None = None) -> list[str]:
    env = [d for d in os.environ.get("RETIRESAFE_OWNED_DOMAINS", "").replace(" ", "").split(",") if d]
    return sorted({d.lower().strip(".") for d in env + (extra or [])})


def is_owned(host: str, domains: list[str]) -> bool:
    h = host.lower().strip(".")
    return any(h == d or h.endswith("." + d) for d in domains)


def split(hosts: list[str], domains: list[str]) -> tuple[list[str], list[str]]:
    ok = [h for h in hosts if is_owned(h, domains)]
    return ok, [h for h in hosts if not is_owned(h, domains)]
