"""Download the real traffic data the demo and pilot use (works on Windows, macOS, Linux).

    python scripts/get_data.py

Downloads NASA-HTTP July and August 1995 logs (about 37 MB compressed) from the GitHub
mirror of the Internet Traffic Archive, verifies their SHA-256, and writes
data/nasa-http/nasa_jul_aug_1995.log (about 370 MB) plus the individual July log.
"""
from __future__ import annotations

import gzip
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "nasa-http"
BASE = "https://raw.githubusercontent.com/greymd/NASA-HTTP/main/"
FILES = {   # sha256 recorded when the research was done (2026-10-01)
    "NASA_access_log_Jul95.gz": "199109ed0f273e095da6ccd5fc9dc4cd8bb58daa06d62135e62090fea9d27488",
    "NASA_access_log_Aug95.gz": "14995aed0ba4558ab832613ebea9a3ef2d87cb4297fc67f5694e0032bbb6b788",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(name: str, digest: str) -> Path:
    dest = OUT / name
    if dest.exists() and sha256(dest) == digest:
        print(f"  {name}: already present, checksum OK")
        return dest
    print(f"  {name}: downloading ...", flush=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(BASE + name, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    got = sha256(tmp)
    if got != digest:
        tmp.unlink()
        sys.exit(f"checksum mismatch for {name}: expected {digest}, got {got}")
    tmp.replace(dest)
    print(f"  {name}: checksum OK")
    return dest


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Writing to {OUT}")
    gz = [download(n, d) for n, d in FILES.items()]
    jul = OUT / "NASA_access_log_Jul95"
    combined = OUT / "nasa_jul_aug_1995.log"
    if not jul.exists():
        with gzip.open(gz[0], "rb") as src, open(jul, "wb") as dst:
            shutil.copyfileobj(src, dst)
    print("  building nasa_jul_aug_1995.log ...", flush=True)
    with open(combined, "wb") as dst:
        for g in gz:
            with gzip.open(g, "rb") as src:
                data = src.read()
            dst.write(data)
            if not data.endswith(b"\n"):   # July ends with a truncated record; keep files on separate lines
                dst.write(b"\n")
    print(f"Done. {combined} ({combined.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
