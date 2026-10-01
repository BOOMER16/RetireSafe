"""Static scan of a source tree for references to retiring resources.

Finds S3 bucket references (virtual-hosted and path-style URLs, s3:// URIs,
ARNs, SDK ``Bucket=`` arguments) and literal hostnames (provider endpoints and
custom domains that DNS maps to the resource). Records the integrity controls
that would make a reclaimed resource harmless to that consumer:

* ``sri``  - the referencing HTML tag carries an ``integrity=`` hash (W3C SRI)
* ``expected_bucket_owner`` - the file passes ExpectedBucketOwner on S3 API calls
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .. import names

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".terraform", "dist", "build", ".tox"}
MAX_BYTES = 2_000_000
SRI = re.compile(r"\bintegrity\s*=\s*[\"']sha(256|384|512)-", re.I)
EXPECTED_OWNER = re.compile(r"ExpectedBucketOwner|expected_bucket_owner|x-amz-expected-bucket-owner", re.I)


@dataclass
class CodeHit:
    file: str          # path relative to the repo root
    line: int
    text: str          # the stripped source line (truncated)
    target: str        # bucket name or hostname matched
    target_kind: str   # "s3_bucket" or "hostname"
    integrity_control: str | None


@dataclass
class ScanStats:
    files_scanned: int
    files_skipped_binary: int
    files_skipped_large: int


def _is_binary(chunk: bytes) -> bool:
    return b"\x00" in chunk


def scan(root: str | Path, buckets: set[str], hostnames: set[str]) -> tuple[list[CodeHit], ScanStats]:
    root = Path(root)
    buckets = {b.lower() for b in buckets}
    hostnames = {h.lower().rstrip(".") for h in hostnames}
    host_rx = (re.compile(r"(?<![a-z0-9.-])(" + "|".join(re.escape(h) for h in sorted(hostnames, key=len, reverse=True))
                          + r")(?![a-z0-9-])", re.I) if hostnames else None)
    lit_rx = (re.compile(r"[\"'`](" + "|".join(re.escape(x) for x in sorted(buckets, key=len, reverse=True))
                         + r")[\"'`/]", re.I) if buckets else None)
    hits: list[CodeHit] = []
    scanned = binary = large = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                if p.is_symlink() or not p.is_file():
                    continue
                if p.stat().st_size > MAX_BYTES:
                    large += 1
                    continue
                raw = p.read_bytes()
            except OSError:
                continue
            if _is_binary(raw[:8192]):
                binary += 1
                continue
            scanned += 1
            text = raw.decode("utf-8", errors="replace")
            owner_check = bool(EXPECTED_OWNER.search(text))
            rel = str(p.relative_to(root))
            for i, line in enumerate(text.splitlines(), 1):
                found = [(b, "s3_bucket") for b in names.s3_buckets_in(line) if b in buckets]
                if lit_rx:      # bucket passed as a bare string literal, e.g. download_file("bucket", key)
                    found += [(m.group(1).lower(), "s3_bucket") for m in lit_rx.finditer(line)]
                if host_rx:
                    found += [(m.group(1).lower(), "hostname") for m in host_rx.finditer(line)]
                for target, kind in dict.fromkeys(found):
                    control = None
                    if SRI.search(line):
                        control = "sri"
                    elif owner_check and kind == "s3_bucket":
                        control = "expected_bucket_owner"
                    hits.append(CodeHit(rel, i, line.strip()[:240], target, kind, control))
    return hits, ScanStats(scanned, binary, large)
