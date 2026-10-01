"""Read ``terraform show -json <planfile>`` output.

Extracts the resources a change would delete (or replace) and every other
resource in the prior state, so that infrastructure references that survive the
change can be found.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..knowledge import providers
from ..models import RetiringResource


@dataclass
class StateResource:
    address: str
    type: str
    values: dict
    deleted_in_change: bool


@dataclass
class PlanView:
    terraform_version: str | None
    format_version: str | None
    provider_regions: dict[str, str]
    retiring: list[RetiringResource]
    state: list[StateResource]
    unsupported_deletions: list[str]


def _walk_modules(mod: dict):
    for r in mod.get("resources", []) or []:
        yield r
    for child in mod.get("child_modules", []) or []:
        yield from _walk_modules(child)


def _provider_regions(plan: dict) -> dict[str, str]:
    out = {}
    for key, cfg in (plan.get("configuration", {}).get("provider_config", {}) or {}).items():
        region = (cfg.get("expressions", {}).get("region", {}) or {}).get("constant_value")
        if region:
            out[key] = region
            out.setdefault(cfg.get("name", key), region)
    return out


def load(path: str | Path) -> PlanView:
    plan = json.loads(Path(path).read_text())
    if "resource_changes" not in plan and "prior_state" not in plan:
        raise ValueError(f"{path}: not a Terraform plan JSON (run `terraform show -json plan.out`)")
    regions = _provider_regions(plan)
    retiring, unsupported, deleted = [], [], set()
    for rc in plan.get("resource_changes", []) or []:
        if rc.get("mode", "managed") != "managed":
            continue
        actions = rc.get("change", {}).get("actions", [])
        if "delete" not in actions:
            continue
        deleted.add(rc["address"])
        action = "delete" if actions == ["delete"] else "replace"
        before = rc["change"].get("before") or {}
        ptype = rc["type"]
        pname = rc.get("provider_name", "")
        short = pname.rsplit("/", 1)[-1]
        view = providers.view(ptype, before, regions.get(short) or regions.get(pname))
        if view is None:
            unsupported.append(f"{rc['address']} ({ptype})")
        retiring.append(RetiringResource(
            address=rc["address"], type=ptype, provider=pname, action=action,
            name=view.name if view else None, region=view.region if view else None,
            attributes=before, endpoints=view.endpoints if view else []))
    state = []
    prior = (plan.get("prior_state") or {}).get("values", {}).get("root_module", {})
    for r in _walk_modules(prior):
        if r.get("mode", "managed") != "managed":
            continue
        state.append(StateResource(r["address"], r["type"], r.get("values") or {}, r["address"] in deleted))
    return PlanView(plan.get("terraform_version"), plan.get("format_version"), regions,
                    retiring, state, unsupported)
