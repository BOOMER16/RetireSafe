"""Evidence record: the auditable output of an assessment."""
from __future__ import annotations

import platform
import uuid
from datetime import datetime, timezone

from .. import __version__, redact
from ..engine.assess import AssessmentResult
from ..knowledge.fingerprints import CATALOGUE_COMMIT
from ..knowledge.providers import RULES_VERSION
from ..knowledge.sources import SOURCES
from ..models import Verdict, to_dict

SCHEMA = "retiresafe.evidence/v1"
GATE_PASS = {Verdict.RELEASE, Verdict.NOT_NAME_BEARING}


def gate(result: AssessmentResult) -> dict:
    counts: dict[str, int] = {}
    for a in result.resources:
        counts[a.verdict.value] = counts.get(a.verdict.value, 0) + 1
    passed = all(a.verdict in GATE_PASS for a in result.resources)
    return {"passed": passed, "verdict_counts": counts,
            "summary": ("all retiring resources may be released" if passed else
                        "deletion must not proceed as planned; see blocked / tombstone / review resources")}


def record(result: AssessmentResult, policy_dict: dict, assessment_id: str | None = None) -> dict:
    cited = set()
    resources = []
    for a in result.resources:
        d = to_dict(a)
        for p in a.paths:
            for c in p.conditions.values():
                cited |= {e[4:] for e in c.evidence_ids if e.startswith("src:")}
        cited |= {e[4:] for e in a.reclaimable.evidence_ids if e.startswith("src:")}
        resources.append(d)
    return {
        "schema": SCHEMA,
        "assessment_id": assessment_id or str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "as_of": result.as_of.isoformat(),
        "tool": {"name": "retiresafe", "version": __version__, "rules_version": RULES_VERSION,
                 "fingerprint_catalogue_commit": CATALOGUE_COMMIT, "python": platform.python_version(),
                 "redaction": {"terraform_sensitivity_mask": True, "attribute_minimisation": True,
                               "secret_rules": {k: v for k, v in redact.rules()[1].items()}}},
        "policy": policy_dict,
        "inputs": result.inputs,
        "plan": {"terraform_version": result.plan.terraform_version, "format_version": result.plan.format_version,
                 "retiring": [r.address for r in result.plan.retiring]},
        "gate": gate(result),
        "resources": resources,
        "evidence": [to_dict(e) for e in result.evidence],
        "parse_stats": result.parse_stats,
        "scan_stats": result.scan_stats,
        "not_checked": result.not_checked,
        "sources": {k: SOURCES[k] for k in sorted(cited) if k in SOURCES},
    }


def markdown(rec: dict) -> str:
    g = rec["gate"]
    out = [f"# RetireSafe assessment {rec['assessment_id']}", "",
           f"*As of {rec['as_of']} · rules {rec['tool']['rules_version']} · policy {rec['policy']['mode']}*", "",
           f"**Gate: {'PASS' if g['passed'] else 'FAIL'}**: {g['summary']}", ""]
    for r in rec["resources"]:
        res = r["resource"]
        out += [f"## {res['address']}: **{r['verdict'].upper()}**", "",
                f"Name `{res['name']}` · reclaimable: **{r['reclaimable']['value']}** ({r['reclaimable']['reason']})", ""]
        out += [f"- {x}" for x in r["reasons"]] + [""]
        if r["references"]:
            out += ["| Reference | Kind | Path status | Broken by |", "|---|---|---|---|"]
            status = {p["reference_id"]: p for p in r["paths"]}
            for ref in r["references"]:
                p = status.get(ref["id"], {})
                out.append(f"| `{ref['location']}` | {ref['kind']} | {p.get('status','-')} | "
                           f"{', '.join(p.get('broken_by', [])) or '-'} |")
            out.append("")
        for t in r["traffic"]:
            q = t["quarantine_days_conservative"]
            out.append(f"- Traffic `{t['source']}`: {t['requests']} requests, {t['distinct_clients']} clients "
                       f"({t['external_clients']} external), window {t['window_days']:.1f} d, silent "
                       f"{t['silence_days'] if t['silence_days'] is not None else 'n/a'} d, conservative quarantine "
                       f"{('%.1f d' % q) if q else 'n/a'}")
        out.append(f"- Risk interval: {r['risk_interval'][0]:.3f} to {r['risk_interval'][1]:.3f}")
        for p in r["patches"]:
            out += ["", f"### Patch: {p['title']}", "```", p["content"].rstrip(), "```"]
        out += ["", "Not checked: " + "; ".join(r["not_checked"]), ""]
    if rec["not_checked"]:
        out += ["## Outside coverage", ""] + [f"- {x}" for x in rec["not_checked"]]
    return "\n".join(out) + "\n"
