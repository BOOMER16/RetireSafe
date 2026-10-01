"""Where the optional real datasets live: $RS_DATA, else <repo>/data."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    env = os.environ.get("RS_DATA")
    return Path(env) if env else REPO_ROOT / "data"


def nasa_log(name: str = "nasa_jul_aug_1995.log") -> Path:
    return data_dir() / "nasa-http" / name
