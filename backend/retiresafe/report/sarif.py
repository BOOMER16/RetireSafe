"""SARIF 2.1.0 output for GitHub code scanning.

Follows the OASIS SARIF 2.1.0 schema and the properties GitHub documents as required
(github/docs, content/code-security/reference/code-scanning/sarif-files/sarif-support.md):
tool.driver.name and rules[] (id, shortDescription, fullDescription, help), and for every result
message.text, locations[].physicalLocation (artifactLocation.uri, region start/end line and
column) and partialFingerprints.

Code references point at the exact file and line. DNS and infrastructure references have no file
in the repository; they are attached to ``anchor`` (for example ``main.tf``) when one is given,
and otherwise left out of the SARIF (they remain in the evidence record).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .. import __version__

SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
RULES = {
    "RS001": ("hijackable-reference", "error", "8.1",
              "Reference would follow a cloud name that another account can claim after this deletion",
              "Every takeover condition holds for this reference: the plan releases the name, another account "
              "can register it, the reference survives, consumers remain and nothing checks ownership or "
              "integrity. Remove or migrate the reference, add an owner/integrity check, or keep the name."),
    "RS002": ("unverified-reference", "warning", "5.0",
              "Reference to a released cloud name whose risk could not be ruled out",
              "At least one takeover condition could not be evaluated (for example no access logs). "
              "Supply the missing evidence or treat the reference as hijackable."),
    "RS003": ("informational-reference", "note", None,
              "Mention of a released cloud name that does not carry traffic",
              "The name appears in a comment, in prose, or as a quoted string outside bucket position. "
              "It cannot route users or software to a new owner, but it may mislead readers."),
}
STATUS_RULE = {"hijackable": "RS001", "unknown": "RS002", "waived": "RS002"}


def _region(repo: Path | None, rel: str, line: int, target: str) -> dict:
    col_start, col_end = 1, 2
    if repo:
        try:
            text = (repo / rel).read_text(encoding="utf-8", errors="replace").splitlines()[line - 1]
            idx = text.lower().find(target.lower())
            if idx >= 0:
                col_start, col_end = idx + 1, idx + 1 + len(target)
            else:
                col_end = max(2, len(text) + 1)
        except (OSError, IndexError):
            pass
    return {"startLine": line, "startColumn": col_start, "endLine": line, "endColumn": col_end}


def build(rec: dict, repos: dict[str, Path], anchor: str | None = None) -> dict:
    results = []
    ids = list(RULES)
    for r in rec["resources"]:
        res = r["resource"]
        status = {p["reference_id"]: p for p in r["paths"]}
        for ref in r["references"]:
            p = status.get(ref["id"])
            if not p:
                continue
            rule = "RS003" if ref.get("method") == "mention" or ref.get("context") == "comment" else \
                STATUS_RULE.get(p["status"])
            if rule is None:
                continue                      # safe paths are not findings
            if ref["kind"] == "code":
                label, _, rest = ref["location"].partition("::")
                rel, _, line = rest.rpartition(":")
                loc_uri, region = rel, _region(repos.get(label), rel, int(line), ref["target_name"])
            elif anchor:
                loc_uri, region = anchor, {"startLine": 1, "startColumn": 1, "endLine": 1, "endColumn": 2}
            else:
                continue
            msg = (f"{res['address']} ({res['name']}) is being deleted and its name can be claimed by another "
                   f"account; this {ref['kind']} reference ({ref['location']}) would follow it.")
            if p["status"] == "waived":
                msg += " Risk accepted by a waiver; see the evidence record."
            fp = hashlib.sha256("|".join([rule, res["address"], ref["kind"], ref["location"].split("::")[-1].rsplit(":", 1)[0],
                                          ref["target_name"], ref["text"]]).encode()).hexdigest()
            results.append({
                "ruleId": rule, "ruleIndex": ids.index(rule), "level": RULES[rule][1],
                "message": {"text": msg},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": loc_uri}, "region": region}}],
                "partialFingerprints": {"retiresafeReference/v1": fp},
                "properties": {"resource": res["address"], "verdict": r["verdict"], "path_status": p["status"],
                               "assessment_id": rec["assessment_id"]},
            })
    rules = []
    for rid, (name, level, sev, short, full) in RULES.items():
        rule = {"id": rid, "name": name, "shortDescription": {"text": short}, "fullDescription": {"text": full},
                "help": {"text": full}, "defaultConfiguration": {"level": level},
                "properties": {"tags": ["security", "subdomain-takeover", "cloud-retirement"]}}
        if sev:
            rule["properties"]["security-severity"] = sev
        rules.append(rule)
    return {"$schema": SCHEMA, "version": "2.1.0", "runs": [{
        "tool": {"driver": {"name": "RetireSafe", "version": __version__,
                            "informationUri": "https://github.com/BOOMER16/RetireSafe", "rules": rules}},
        "results": results,
        "properties": {"gate": rec["gate"], "assessment_id": rec["assessment_id"]}}]}
