"""Remediation patches for a resource assessment.

Patches are proposals for a human to review and apply; nothing is executed.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from .. import redact
from ..analysis.traffic import Policy
from ..collectors.dns_zone import DnsRecord
from ..knowledge.providers import (ACCOUNT_REGIONAL_NAME, AZURE_LABELLED, AZURE_NAMED, AZURE_WEBAPP_TYPES,
                                   EB_TYPES, S3_TYPES)
from ..models import Patch, PathAssessment, Reference, RefKind, RetiringResource, Verdict


def _hcl_label(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_") or "retained"


def route53_delete_batch(records: list[DnsRecord], comment: str) -> Patch | None:
    changes = []
    for r in records:
        rs = {k: v for k, v in r.raw.items() if k in ("Name", "Type", "TTL", "ResourceRecords", "AliasTarget",
                                                       "SetIdentifier", "Weight", "Region", "Failover")}
        if rs:
            changes.append({"Action": "DELETE", "ResourceRecordSet": rs})
    if not changes:
        return None
    body = json.dumps({"Comment": comment, "Changes": changes}, indent=2)
    return Patch("route53_change_batch", "Delete the surviving DNS records (Route 53 change batch)",
                 body + "\n\n# apply with:\n# aws route53 change-resource-record-sets "
                 "--hosted-zone-id <ZONE_ID> --change-batch file://change-batch.json",
                 [r.location for r in records])


def zone_file_advice(records: list[DnsRecord]) -> Patch | None:
    if not records:
        return None
    lines = [f"{r.name}.  {r.ttl or ''}  IN  {r.type}  {' '.join(r.values)}" for r in records]
    return Patch("advice", "Remove these records from the zone file",
                 "Delete (or repoint to a resource you keep) the following records, then bump the SOA serial:\n"
                 + "\n".join(lines), [r.location for r in records])


def code_patch(repo_root: Path, refs: list[Reference], old: str, new: str) -> Patch | None:
    files = sorted({r.location.rsplit(":", 1)[0] for r in refs})
    diffs = []
    for rel in files:
        p = repo_root / rel
        try:
            before = p.read_text(encoding="utf-8")
        except OSError:
            continue
        after = rename(before, old, new)
        if after != before:
            diffs.append("".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                      f"a/{rel}", f"b/{rel}")))
    if not diffs:
        return None
    shown = "".join(redact.scrub(line) for line in "".join(diffs).splitlines(True))
    return Patch("code_diff", f"Rewrite references from {old} to {new}", shown, files,
                 {"type": "rename", "old": old, "new": new, "files": files})


def rename(text: str, old: str, new: str) -> str:
    return re.sub(rf"(?<![a-z0-9.-]){re.escape(old)}(?![a-z0-9-])", new, text)


def tombstone(res: RetiringResource, policy: Policy, chosen: str | None = None) -> Patch:
    if res.type in S3_TYPES:
        label = _hcl_label(res.address.split(".")[-1])
        acct = policy.org_account_ids[0] if policy.org_account_ids else "<ACCOUNT_ID>"
        region = res.region or "<REGION>"
        prefix = re.sub(r"[^a-z0-9-]", "-", (res.name or "bucket").lower())[:40].strip("-")
        new_name = chosen or f"{prefix}-{acct}-{region}-an"
        body = f'''# Tombstone: keep owning the bucket name, serve nothing, and record who still asks for it.
# 1. empty the bucket (objects and versions) and remove website/CORS configuration;
# 2. keep these resources until a balanced-mode RetireSafe run, fed by the tombstone's own
#    access logs, shows no remaining consumers. Requests now get 403 (a "brownout" that makes
#    hidden consumers visible) and land in the access logs.
variable "{label}_log_bucket" {{
  description = "Existing bucket that receives S3 server access logs"
  type        = string
}}

resource "aws_s3_bucket" "{label}" {{
  bucket = "{res.name}"
  lifecycle {{
    prevent_destroy = true
  }}
}}

resource "aws_s3_bucket_public_access_block" "{label}" {{
  bucket                  = aws_s3_bucket.{label}.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

resource "aws_s3_bucket_policy" "{label}" {{
  bucket = aws_s3_bucket.{label}.id
  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Sid       = "TombstoneNoObjects"
      Effect    = "Deny"
      Principal = "*"
      Action    = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      Resource  = "${{aws_s3_bucket.{label}.arn}}/*"
    }}]
  }})
}}

resource "aws_s3_bucket_logging" "{label}" {{
  bucket        = aws_s3_bucket.{label}.id
  target_bucket = var.{label}_log_bucket
  target_prefix = "retiresafe-tombstone/{res.name}/"
}}

# If the content must move, create its replacement in your account regional namespace,
# which other accounts cannot claim (format verified from the AWS SDK model):
#   bucket           = "{new_name}"
#   bucket_namespace = "account-regional"
'''
        if ACCOUNT_REGIONAL_NAME.match(new_name) is None:
            body += "#   (fill in ACCOUNT_ID and REGION to obtain a valid account-regional name)\n"
        return Patch("terraform_hcl", f"Tombstone {res.address}: keep the name, drop the content", body, [res.address])
    if res.type == "aws_eip":
        label = _hcl_label(res.address.split(".")[-1])
        return Patch("terraform_hcl", f"Keep {res.address} allocated", f'''# Keep the Elastic IP allocated (unassociated) so no other account can be given {res.name}
# while DNS records still point at it. Release it after the records are gone.
resource "aws_eip" "{label}" {{
  domain = "vpc"
  lifecycle {{
    prevent_destroy = true
  }}
}}
''', [res.address])
    if res.type in AZURE_NAMED or res.type in AZURE_LABELLED:
        return Patch("advice", f"Tombstone {res.address}",
                     f"Keep {res.address} (name {res.name!r}) in place with an azurerm_management_lock "
                     "(CanNotDelete) and no content until every reference is gone. For container groups and "
                     "public IPs, recreate replacements with a reuse scope (dns_name_label_reuse_policy / "
                     "domain_name_label_scope = \"NoReuse\") so their hostnames cannot be claimed by others.",
                     [res.address])
    if res.type in AZURE_WEBAPP_TYPES:
        return Patch("advice", f"Tombstone {res.address}",
                     f"Keep the app name {res.name!r} allocated (stop the app or move it to a free plan) instead "
                     "of deleting it. Create replacements with autoGeneratedDomainNameLabelScope set (for example "
                     "NoReuse) so their default hostnames cannot be re-used by another tenant.", [res.address])
    if res.type in EB_TYPES:
        return Patch("advice", f"Tombstone {res.address}",
                     f"The CNAME prefix {res.name!r} returns to the shared pool when the environment is terminated. "
                     "Keep a minimal environment holding the prefix until every reference is gone, or remove the "
                     "references first.", [res.address])
    return Patch("advice", f"Retain {res.address}", "Keep the resource name allocated.", [res.address])


def owner_check_advice(refs: list[Reference], policy: Policy) -> Patch | None:
    sdk = [r for r in refs if r.kind == RefKind.CODE and r.integrity_control is None and "Bucket" in r.text]
    if not sdk:
        return None
    acct = policy.org_account_ids[0] if policy.org_account_ids else "<ACCOUNT_ID>"
    return Patch("advice", "Add an owner check to S3 API calls",
                 f"Pass ExpectedBucketOwner='{acct}' on these S3 API calls; S3 then refuses a bucket owned by any "
                 "other account (HTTP 403):\n" + "\n".join(f"  {r.location}: {r.text}" for r in sdk),
                 [r.location for r in sdk])


HOLDING_COST = {
    "s3": ("No storage charge once the bucket is empty. It still counts toward the account's bucket quota "
           "(default 10,000) and buckets beyond the first 2,000 per account carry a per-bucket monthly fee.",
           ["src:aws-s3-bucket-quota-2024"]),
    "eip": ("An idle Elastic IP is billed as a public IPv4 address: USD 0.005 per hour (about USD 3.65 per "
            "30-day month) since 1 February 2024.", ["src:aws-ipv4-charge-2024"]),
    "eb": ("Holding the CNAME prefix needs a running environment and its instance costs; prefer removing the "
           "references and then releasing.", []),
    "azure": ("Resource-specific; keep the lowest tier with no content and a CanNotDelete lock.", []),
}


def tombstone_plan(res: RetiringResource, traffic: list, policy: Policy, as_of) -> dict:
    from datetime import timedelta
    days = policy.min_window_days
    for t in traffic:
        if t.requests and t.quarantine_days_conservative:
            days = max(days, t.quarantine_days_conservative)
    kind = ("s3" if res.type in S3_TYPES else "eip" if res.type == "aws_eip" else "eb" if res.type in EB_TYPES
            else "azure")
    cost, srcs = HOLDING_COST[kind]
    return {
        "review_after": (as_of + timedelta(days=days)).date().isoformat(),
        "review_basis_days": round(days, 1),
        "holding_cost": cost, "sources": srcs,
        "release_path": ("Keep the tombstone's access logging on. After the review date, run RetireSafe in "
                         "balanced mode with those logs: if no surviving reference is hijackable and the logs "
                         "are silent past the quarantine, the name can be released."),
    }


def build(res: RetiringResource, verdict: Verdict, refs: list[Reference], paths: list[PathAssessment],
          dns_by_ref: dict[str, DnsRecord], repo_roots: dict[str, Path], policy: Policy,
          migrate_to: dict[str, str]) -> list[Patch]:
    if verdict in (Verdict.RELEASE, Verdict.NOT_NAME_BEARING):
        return []
    live = {p.reference_id for p in paths if p.status != "safe"}
    patches: list[Patch] = []
    dns_live = [dns_by_ref[r.id] for r in refs if r.id in live and r.id in dns_by_ref]
    r53 = [d for d in dns_live if d.raw]
    bind = [d for d in dns_live if not d.raw]
    for p in (route53_delete_batch(r53, f"RetireSafe: remove references to {res.name}"), zone_file_advice(bind)):
        if p:
            patches.append(p)
    code = [r for r in refs if r.kind == RefKind.CODE and r.id in live]
    new = migrate_to.get(res.name or "")
    if new and code:
        by_repo: dict[str, list[Reference]] = {}
        for r in code:
            by_repo.setdefault(r.location.split("::", 1)[0], []).append(r)
        for repo, rs in by_repo.items():
            local = [Reference(**{**r.__dict__, "location": r.location.split("::", 1)[1]}) for r in rs]
            targets = {r.target_name for r in rs}
            for old in sorted(targets, key=len, reverse=True):
                p = code_patch(repo_roots[repo], [x for x in local if x.target_name == old], old,
                               new if old == res.name else old.replace(res.name or "", new))
                if p:
                    patches.append(p)
    elif code:
        patches.append(Patch("advice", "Update or remove code references",
                             "\n".join(f"  {r.location}: {r.text}" for r in code), [r.location for r in code]))
    adv = owner_check_advice([r for r in refs if r.id in live], policy)
    if adv:
        patches.append(adv)
    iac = [r for r in refs if r.kind == RefKind.IAC and r.id in live]
    if iac:
        patches.append(Patch("advice", "Update infrastructure that still references the resource",
                             "\n".join(f"  {r.location}: {r.text}" for r in iac), [r.location for r in iac]))
    if verdict in (Verdict.TOMBSTONE, Verdict.BLOCK, Verdict.REVIEW):
        patches.append(tombstone(res, policy, new))
    return patches
