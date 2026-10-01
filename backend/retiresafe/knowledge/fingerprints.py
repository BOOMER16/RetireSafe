"""Loader for the vendored can-i-take-over-xyz fingerprint catalogue (CC BY 4.0)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

CATALOGUE = Path(__file__).parent / "data" / "can-i-take-over-xyz.fingerprints.json"
CATALOGUE_COMMIT = "5bd4e12837911c8475486f1da922c9b9c706e632"
S3_HOST = re.compile(r"(^|\.)s3[.-]([a-z0-9-]+\.)*amazonaws\.com$|s3-website")


@lru_cache(maxsize=1)
def entries() -> list[dict]:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _suffixes() -> list[tuple[str, dict]]:
    out = []
    for fp in entries():
        for c in fp.get("cname", []):
            c = c.lower().strip(".")
            if re.search(r"[a-z]", c):  # skip bare IP entries
                out.append((c, fp))
    return sorted(out, key=lambda x: -len(x[0]))


def match(host: str) -> dict | None:
    """Return the catalogue entry whose CNAME suffix matches ``host`` (longest suffix wins)."""
    h = host.lower().rstrip(".")
    for suf, fp in _suffixes():
        if h == suf or h.endswith("." + suf):
            return fp
    if S3_HOST.search(h):
        return next(f for f in entries() if f["service"] == "AWS/S3")
    return None
