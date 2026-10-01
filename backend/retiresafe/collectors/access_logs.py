"""Access-log readers.

Supported formats (validated against real samples, see tests/fixtures/README.md):

* ``clf``        NCSA Common / Combined Log Format (e.g. NASA-HTTP 1995, Apache, nginx)
* ``s3``         Amazon S3 server access logs
* ``cloudfront`` Amazon CloudFront standard logs (tab separated, ``#Fields:`` header)

Each reader yields ``Request`` rows. Lines that cannot be parsed are counted,
never guessed.
"""
from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote

CLF = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(?:(\S+) (\S+?)(?: \S+)?)?" (\d{3}|-) (\d+|-)')
S3_TOKENS = re.compile(r'\[[^\]]*\]|"(?:[^"\\]|\\.)*"|\S+')


@dataclass
class Request:
    ts: datetime          # timezone-aware, UTC
    client: str           # IP address or client hostname
    host: str | None      # virtual host / bucket endpoint if the format records it
    bucket: str | None    # S3 bucket (s3 format only)
    path: str             # URL path without query string ("-" if absent)
    status: int | None
    requester: str | None = None   # S3 requester (canonical id / ARN) if present


@dataclass
class ParseStats:
    lines: int = 0
    parsed: int = 0
    failed: int = 0


def _open(path: Path):
    return gzip.open(path, "rt", encoding="latin-1") if path.suffix == ".gz" else open(path, encoding="latin-1")


_MON = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                     "Nov", "Dec"), 1)}
_TZ: dict[str, timezone] = {}


def _clf_time(s: str) -> datetime:
    """Parse '01/Jul/1995:00:00:01 -0400' (fast path; falls back to strptime for anything unusual)."""
    try:
        if len(s) == 26 and s[2] == "/" and s[6] == "/" and s[11] == ":" and s[20] == " ":
            tz = _TZ.get(s[21:])
            if tz is None:
                sign = -1 if s[21] == "-" else 1
                from datetime import timedelta
                tz = _TZ.setdefault(s[21:], timezone(sign * timedelta(hours=int(s[22:24]), minutes=int(s[24:26]))))
            return datetime(int(s[7:11]), _MON[s[3:6]], int(s[0:2]), int(s[12:14]), int(s[15:17]),
                            int(s[18:20]), tzinfo=tz).astimezone(timezone.utc)
    except (KeyError, ValueError):
        pass
    return datetime.strptime(s, "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)


def read_clf(path: str | Path, host: str | None, stats: ParseStats) -> Iterator[Request]:
    with _open(Path(path)) as f:
        for ln in f:
            stats.lines += 1
            m = CLF.match(ln)
            if not m:
                stats.failed += 1
                continue
            client, ts, _meth, url, status, _size = m.groups()
            try:
                t = _clf_time(ts)
            except ValueError:
                stats.failed += 1
                continue
            stats.parsed += 1
            yield Request(t, client, host, None, url.split("?")[0] if url else "-",
                          int(status) if status.isdigit() else None)


def read_s3(path: str | Path, stats: ParseStats) -> Iterator[Request]:
    with _open(Path(path)) as f:
        for ln in f:
            if not ln.strip():
                continue
            stats.lines += 1
            tok = S3_TOKENS.findall(ln)
            if len(tok) < 10 or not tok[2].startswith("["):
                stats.failed += 1
                continue
            try:
                t = _clf_time(tok[2][1:-1])
            except ValueError:
                stats.failed += 1
                continue
            uri = tok[8].strip('"').split(" ")
            path_ = uri[1].split("?")[0] if len(uri) > 1 else "-"
            # field order per the AWS S3 server access log format: 22 = Host Header
            host = tok[22].lower() if len(tok) > 22 and tok[22] != "-" else None
            stats.parsed += 1
            yield Request(t, tok[3], host, tok[1].lower(), path_,
                          int(tok[9]) if tok[9].isdigit() else None, tok[4] if tok[4] != "-" else None)


def read_cloudfront(path: str | Path, stats: ParseStats) -> Iterator[Request]:
    fields: list[str] = []
    with _open(Path(path)) as f:
        for ln in f:
            if ln.startswith("#Fields:"):
                fields = ln[len("#Fields:"):].split()
                continue
            if ln.startswith("#") or not ln.strip():
                continue
            stats.lines += 1
            parts = ln.rstrip("\n").split("\t")
            if not fields or len(parts) < len(fields) - 2:
                stats.failed += 1
                continue
            row = dict(zip(fields, parts))
            try:
                t = datetime.strptime(f"{row['date']} {row['time']}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except (KeyError, ValueError):
                stats.failed += 1
                continue
            host = row.get("x-host-header") or row.get("cs(Host)")
            status = row.get("sc-status", "")
            stats.parsed += 1
            yield Request(t, row.get("c-ip", "-"), host.lower() if host and host != "-" else None, None,
                          unquote(row.get("cs-uri-stem", "-")), int(status) if status.isdigit() else None)


def read(path: str | Path, fmt: str, host: str | None, stats: ParseStats) -> Iterator[Request]:
    if fmt == "clf":
        return read_clf(path, host, stats)
    if fmt == "s3":
        return read_s3(path, stats)
    if fmt == "cloudfront":
        return read_cloudfront(path, stats)
    raise ValueError(f"unknown log format {fmt!r} (expected clf, s3 or cloudfront)")
