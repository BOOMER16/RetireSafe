from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
FIX = BACKEND / "tests" / "fixtures"
PILOT = REPO / "pilot"
GEN = PILOT / "generated"
NASA_JULAUG = Path("/home/user/data/nasa-http/nasa_jul_aug_1995.log")
NASA_JUL = Path("/home/user/data/nasa-http/NASA_access_log_Jul95")


@pytest.fixture
def fix():
    return FIX


@pytest.fixture
def gen():
    return GEN
