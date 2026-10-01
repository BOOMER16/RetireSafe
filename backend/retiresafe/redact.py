"""Keep secrets out of everything RetireSafe stores or shows.

Two layers:

1. Terraform's own sensitivity marks. ``terraform show -json`` prints sensitive values in plain
   text but also emits a parallel mask (``before_sensitive`` for changes, ``sensitive_values`` for
   state). ``by_mask`` replaces every masked leaf.
2. Pattern-based secret detection for free text (code lines, attribute strings) using the
   gitleaks rule set (MIT, vendored at commit b58d3f102cf3, see knowledge/data/gitleaks.toml),
   with gitleaks' keyword prefilter and Shannon-entropy thresholds. Go-only inline flags are
   translated to Python scoped flags; rules that still do not compile are skipped and counted.

Redaction errs towards over-redaction: gitleaks allowlists (for example AWS's documented
EXAMPLE keys) are deliberately not applied, because RetireSafe stores evidence, it does not
triage leaks.
"""
from __future__ import annotations

import math
import re
import tomllib
import warnings
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

GITLEAKS = Path(__file__).parent / "knowledge" / "data" / "gitleaks.toml"
GITLEAKS_COMMIT = "b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b"
MARK = "[REDACTED]"
SENSITIVE = "[sensitive]"

# Attribute names whose values are never stored even when Terraform does not mark them.
SECRET_KEYS = re.compile(r"(passw|secret|token|private_?key|api_?key|access_?key|credential|"
                         r"connection_?string|user_?data|certificate_?body|ssh_?key)", re.I)


def by_mask(values, mask):
    """Replace every value whose mask entry is ``true`` (Terraform plan/state sensitivity mask)."""
    if mask is True:
        return SENSITIVE if values not in (None, "", [], {}) else values
    if isinstance(values, dict):
        m = mask if isinstance(mask, dict) else {}
        return {k: by_mask(v, m.get(k)) for k, v in values.items()}
    if isinstance(values, list):
        m = mask if isinstance(mask, list) else []
        return [by_mask(v, m[i] if i < len(m) else None) for i, v in enumerate(values)]
    return values


def mask_at(mask, path: list[str]) -> bool:
    """True if ``path`` (attribute path, list indices as strings) is masked as sensitive."""
    node = mask
    for p in path:
        if node is True:
            return True
        if isinstance(node, dict):
            node = node.get(p)
        elif isinstance(node, list) and p.isdigit() and int(p) < len(node):
            node = node[int(p)]
        else:
            return False
    return node is True


def _go_to_python(rx: str) -> str:
    """Translate Go RE2 mid-pattern '(?i)' into Python's scoped '(?i:...)'."""
    out = rx
    while True:
        p = out.find("(?i)", 1)
        if p <= 0:
            return out
        depth, i = 0, p + 4
        while i < len(out):
            c = out[i]
            if c == "\\":
                i += 2
                continue
            if c == "[":                       # skip character classes
                j = i + 1
                while j < len(out) and out[j] != "]":
                    j += 2 if out[j] == "\\" else 1
                i = j + 1
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                if depth == 0:
                    break
                depth -= 1
            i += 1
        out = out[:p] + "(?i:" + out[p + 4:i] + ")" + out[i:]


@dataclass
class Rule:
    id: str
    rx: re.Pattern
    keywords: tuple[str, ...]
    entropy: float | None
    group: int | None


@lru_cache(maxsize=1)
def rules() -> tuple[list[Rule], dict]:
    data = tomllib.loads(GITLEAKS.read_text(encoding="utf-8"))
    out, skipped = [], []
    for r in data.get("rules", []):
        if "regex" not in r:
            continue
        src = r["regex"]
        if src.startswith("(?i)") is False and "(?i)" in src:
            src = _go_to_python(src)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                rx = re.compile(src)
        except re.error:
            skipped.append(r["id"])
            continue
        out.append(Rule(r["id"], rx, tuple(k.lower() for k in r.get("keywords", [])), r.get("entropy"),
                        r.get("secretGroup")))
    # AWS secret access keys have no fixed prefix; gitleaks catches them only via generic-api-key.
    out.append(Rule("aws-secret-access-key", re.compile(
        r"(?i)aws_?secret_?(?:access_?)?key[\"'\s]*[:=]\s*[\"']?([A-Za-z0-9/+=]{40})(?![A-Za-z0-9/+=])"),
        ("secret",), None, 1))
    return out, {"loaded": len(out), "skipped": skipped, "commit": GITLEAKS_COMMIT}


def shannon(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def find_secrets(text: str) -> list[tuple[int, int, str]]:
    """(start, end, rule_id) spans of secrets in ``text``."""
    low = text.lower()
    spans = []
    for r in rules()[0]:
        if r.keywords and not any(k in low for k in r.keywords):
            continue
        for m in r.rx.finditer(text):
            g = r.group if r.group is not None else (1 if m.re.groups >= 1 and m.group(1) else 0)
            try:
                s, e = m.span(g)
            except IndexError:
                s, e = m.span(0)
            if s < 0:
                s, e = m.span(0)
            if r.entropy and shannon(text[s:e]) < r.entropy:
                continue
            spans.append((s, e, r.id))
    return spans


def scrub(text: str) -> str:
    """Replace detected secrets with [REDACTED]."""
    spans = sorted(find_secrets(text))
    if not spans:
        return text
    merged = []
    for s, e, _ in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out, pos = [], 0
    for s, e in merged:
        out.append(text[pos:s])
        out.append(MARK)
        pos = e
    out.append(text[pos:])
    return "".join(out)


def minimise(values: dict, keep: set[str]) -> dict:
    """Keep only the attributes the decision needs; drop the rest (data minimisation)."""
    kept = {k: v for k, v in values.items() if k in keep and not SECRET_KEYS.search(k)}
    dropped = sorted(k for k in values if k not in kept)
    if dropped:
        kept["_omitted_attributes"] = len(dropped)
    return kept
