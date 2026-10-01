"""Read ``terraform show -json <planfile>`` output.

Extracts the resources a change would delete (or replace) and every other
resource in the prior state, so that infrastructure references that survive the
change can be found.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .. import redact
from ..knowledge import providers
from ..models import RetiringResource


# Attributes an evidence record may keep about a retiring resource (everything else is dropped).
KEEP_ATTRIBUTES = {
    "id", "arn", "name", "bucket", "bucket_prefix", "bucket_namespace", "region", "location",
    "website_endpoint", "website_domain", "bucket_domain_name", "bucket_regional_domain_name",
    "default_hostname", "default_site_hostname", "cname", "cname_prefix", "endpoint_url",
    "auto_generated_domain_name_label_scope", "domain_name_label", "domain_name_label_scope",
    "dns_name_label", "dns_name_label_reuse_policy", "fqdn", "host_name", "gateway_url",
    "primary_blob_host", "public_ip", "public_dns", "ip_address", "allocation_id", "domain",
    "relative_name", "aliases", "domain_name",
}


@dataclass
class StateResource:
    address: str
    type: str
    values: dict                      # raw values: used for matching only, never stored
    deleted_in_change: bool
    sensitive: dict | bool | None = None   # Terraform's sensitivity mask for ``values``


@dataclass
class PlanView:
    terraform_version: str | None
    format_version: str | None
    provider_regions: dict[str, str]
    retiring: list[RetiringResource]
    state: list[StateResource]
    unsupported_deletions: list[str]
    raw_before: dict[str, dict] = None    # address -> raw "before" values (internal only)


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
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    if "resource_changes" not in plan and "prior_state" not in plan:
        raise ValueError(f"{path}: not a Terraform plan JSON (run `terraform show -json plan.out`)")
    regions = _provider_regions(plan)
    retiring, unsupported, deleted, raw_before = [], [], set(), {}
    for rc in plan.get("resource_changes", []) or []:
        if rc.get("mode", "managed") != "managed":
            continue
        actions = rc.get("change", {}).get("actions", [])
        if "delete" not in actions:
            continue
        deleted.add(rc["address"])
        action = "delete" if actions == ["delete"] else "replace"
        before = rc["change"].get("before") or {}
        raw_before[rc["address"]] = before
        ptype = rc["type"]
        pname = rc.get("provider_name", "")
        short = pname.rsplit("/", 1)[-1]
        view = providers.view(ptype, before, regions.get(short) or regions.get(pname))
        if view is None:
            unsupported.append(f"{rc['address']} ({ptype})")
        retiring.append(RetiringResource(
            address=rc["address"], type=ptype, provider=pname, action=action,
            name=view.name if view else None, region=view.region if view else None,
            attributes=redact.minimise(redact.by_mask(before, rc["change"].get("before_sensitive")),
                                       KEEP_ATTRIBUTES),
            endpoints=view.endpoints if view else []))
    state = []
    prior = (plan.get("prior_state") or {}).get("values", {}).get("root_module", {})
    for r in _walk_modules(prior):
        if r.get("mode", "managed") != "managed":
            continue
        state.append(StateResource(r["address"], r["type"], r.get("values") or {}, r["address"] in deleted,
                                   r.get("sensitive_values")))
    return PlanView(plan.get("terraform_version"), plan.get("format_version"), regions,
                    retiring, state, unsupported, raw_before)
