from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
FIX = BACKEND / "tests" / "fixtures"
PILOT = REPO / "pilot"
GEN = PILOT / "generated"
from retiresafe.paths import nasa_log  # noqa: E402

NASA_JULAUG = nasa_log()
NASA_JUL = nasa_log("NASA_access_log_Jul95")


@pytest.fixture
def fix():
    return FIX


@pytest.fixture
def gen():
    return GEN
