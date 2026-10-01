"""Static scan of a source tree for references to retiring resources.

Finds S3 bucket references (virtual-hosted and path-style URLs, s3:// URIs,
ARNs, SDK ``Bucket=`` arguments, bare quoted names) and literal hostnames
(provider endpoints and custom domains that DNS maps to the resource).

Each hit records *how* it matched (``method``) and *where* it sits (``context``:
code, comment, docs or test), so reviewers and the decision engine can weigh it.
A bare quoted name counts as a reference only in *bucket position* (an identifier or key
containing "bucket", or the bucket argument of a known S3 SDK call). Other quoted occurrences
near S3 code are reported as informational ``mention`` hits that never block; without S3
context they are discarded. Measured on real repositories (validation/scanner_eval.py):
unrestricted literal matching and an "S3 within two lines" rule both produced mostly false
alarms.

Integrity controls that make a reclaimed resource harmless to that consumer:

* ``sri``  - the referencing HTML tag carries an ``integrity=`` hash (W3C SRI)
* ``expected_bucket_owner`` - the file passes ExpectedBucketOwner on S3 API calls
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .. import names, redact

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".terraform", "dist", "build", ".tox"}
MAX_BYTES = 2_000_000
SRI = re.compile(r"\bintegrity\s*=\s*[\"']sha(256|384|512)-", re.I)
EXPECTED_OWNER = re.compile(r"ExpectedBucketOwner|expected_bucket_owner|x-amz-expected-bucket-owner", re.I)
S3_HINT = re.compile(r"(?i)(?<![a-z0-9])(s3a?|buckets?|boto3?|aws|minio|object[_ -]?store)(?![a-z0-9])")
DOC_EXT = {".md", ".rst", ".adoc", ".asciidoc"}     # .txt is docs only inside doc dirs or for README-like names
DOC_NAMES = re.compile(r"^(readme|changelog|changes|history|notice|license|contributing|authors)\b", re.I)
AWS_HINT = re.compile(r"(?i)(?<![a-z0-9])(s3a?|boto3?|botocore|aws|amazonaws)(?![a-z0-9])")
NON_S3_HINT = re.compile(r"(?i)(gs://|\bgcs\b|google|storage\.client|azure|\bwasb|\badls|blob_?service|"
                         r"\bcontainer_name\b)")
PROSE = r"(?i)(?:\b(?P<a>{alt})\b[`'\"]?\s+(?:s3\s+)?bucket\b|\bbucket\s+(?:called\s+|named\s+)?[`'\"]?(?P<b>{alt})\b)"
DOC_DIRS = {"docs", "doc", "documentation", "site", "website"}
TEST_DIRS = {"test", "tests", "testing", "__tests__", "spec", "specs", "fixtures", "testdata"}
HASH_COMMENT = {".py", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".rb", ".r", ".pl",
                ".tf", ".hcl", ".conf", ".env", ".dockerfile", ""}
SLASH_COMMENT = {".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".c", ".h", ".cc", ".cpp", ".cs", ".kt", ".scala",
                 ".php", ".rs", ".swift", ".tf", ".hcl", ".groovy", ".dart"}


@dataclass
class CodeHit:
    file: str          # path relative to the repo root (POSIX separators)
    line: int
    text: str          # the stripped source line (truncated, secrets redacted)
    target: str        # bucket name or hostname matched
    target_kind: str   # "s3_bucket" or "hostname"
    integrity_control: str | None
    method: str = "url"       # url | sdk_argument | hostname | mention (bare quoted name near S3 code)
    context: str = "code"     # code | comment | docs | test


@dataclass
class ScanStats:
    files_scanned: int
    files_skipped_binary: int
    files_skipped_large: int
    literal_matches_discarded: int = 0


def _is_binary(chunk: bytes) -> bool:
    return b"\x00" in chunk


def file_context(rel: str) -> str:
    pp = PurePosixPath(rel)
    parts = {x.lower() for x in pp.parts[:-1]}
    name = pp.name.lower()
    if parts & TEST_DIRS or name.startswith("test_") or re.search(r"(_test|\.test|\.spec)\.[a-z]+$", name):
        return "test"
    if pp.suffix.lower() in DOC_EXT or parts & DOC_DIRS or (pp.suffix.lower() == ".txt" and DOC_NAMES.match(name)):
        return "docs"
    return "code"


def is_comment(line: str, suffix: str) -> bool:
    t = line.lstrip()
    if not t:
        return False
    if suffix in HASH_COMMENT and t.startswith("#") and not t.startswith("#!"):
        return True
    if suffix in SLASH_COMMENT and (t.startswith("//") or t.startswith("/*") or t.startswith("* ") or t == "*"):
        return True
    if suffix in {".html", ".htm", ".xml", ".md", ".vue", ".svg"} and t.startswith("<!--"):
        return True
    return suffix in {".sql", ".lua"} and t.startswith("--")


def _methods(line: str, buckets: set[str]) -> list[tuple[str, str]]:
    out = []
    for rx in (names.S3_VHOST, names.S3_PATH, names.S3_URI, names.S3_ARN):
        out += [(m.group(1).lower(), "url") for m in rx.finditer(line) if m.group(1).lower() in buckets]
    for rx in (names.SDK_BUCKET, names.SDK_CALL):
        out += [(m.group(1), "sdk_argument") for m in rx.finditer(line) if m.group(1) in buckets]
    return out


def scan(root: str | Path, buckets: set[str], hostnames: set[str],
         literal_mode: str = "s3_context") -> tuple[list[CodeHit], ScanStats]:
    root = Path(root)
    buckets = {b.lower() for b in buckets}
    hostnames = {h.lower().rstrip(".") for h in hostnames}
    host_rx = (re.compile(r"(?<![a-z0-9.-])(" + "|".join(re.escape(h) for h in sorted(hostnames, key=len, reverse=True))
                          + r")(?![a-z0-9-])", re.I) if hostnames else None)
    lit_rx = (re.compile(r"[\"'`](" + "|".join(re.escape(x) for x in sorted(buckets, key=len, reverse=True))
                         + r")[\"'`/]") if buckets else None)      # case-sensitive: bucket names are lower case
    alt = "|".join(re.escape(x) for x in sorted(buckets, key=len, reverse=True))
    prose_rx = re.compile(PROSE.replace("{alt}", alt)) if buckets else None
    hits: list[CodeHit] = []
    scanned = binary = large = discarded = 0
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
            rel = p.relative_to(root).as_posix()
            fctx = file_context(rel)
            suffix = p.suffix.lower() if p.suffix else ("" if not p.name.lower().endswith("dockerfile") else "")
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                found = _methods(line, buckets)
                if any(m == "sdk_argument" for _, m in found):
                    # bucket-position arguments are provider-agnostic; in GCS / Azure code they are not S3
                    near = "\n".join(lines[max(0, i - 6):i + 5])
                    if not AWS_HINT.search(near) and (NON_S3_HINT.search(near) or NON_S3_HINT.search(rel)):
                        found = [(t, "mention" if m == "sdk_argument" else m) for t, m in found]
                if prose_rx:
                    found += [((m.group("a") or m.group("b")).lower(), "mention") for m in prose_rx.finditer(line)]
                if lit_rx:      # bucket passed as a bare string literal, e.g. download_file("bucket", key)
                    for m in lit_rx.finditer(line):
                        window = "\n".join(lines[max(0, i - 3):i + 2])
                        if literal_mode == "any":
                            found.append((m.group(1), "literal"))
                        elif S3_HINT.search(window):
                            found.append((m.group(1), "mention"))   # informational: never blocks
                        else:
                            discarded += 1
                if host_rx:
                    found += [(m.group(1).lower(), "hostname") for m in host_rx.finditer(line)]
                seen: dict[str, str] = {}
                for target, method in found:                    # best method per target per line
                    if target not in seen or (seen[target] in ("literal", "mention") and
                                              method not in ("literal", "mention")):
                        seen[target] = method
                ctx = "comment" if is_comment(line, suffix) else fctx
                for target, method in seen.items():
                    kind = "hostname" if method == "hostname" else "s3_bucket"
                    control = None
                    if SRI.search(line):
                        control = "sri"
                    elif owner_check and kind == "s3_bucket":
                        control = "expected_bucket_owner"
                    hits.append(CodeHit(rel, i, redact.scrub(line.strip())[:240], target, kind, control,
                                        method, ctx))
    return hits, ScanStats(scanned, binary, large, discarded)
