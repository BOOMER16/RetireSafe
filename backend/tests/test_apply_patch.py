"""The pure-Python patch applier reproduces exactly what the generated diff describes."""
import shutil

import pytest

from conftest import PILOT
from retiresafe.engine import apply_patch, remediate
from retiresafe.models import Reference, RefKind


def _diff(repo, old, new):
    refs = [Reference("r", RefKind.CODE, "index.html:14", "", old)]
    return remediate.code_patch(repo, refs, old, new).content


def test_apply_matches_direct_rewrite(tmp_path):
    repo = tmp_path / "app"
    shutil.copytree(PILOT / "app", repo)
    old, new = "rs-pilot-event-assets-2025", "rs-pilot-event-assets-123456789012-us-east-1-an"
    expected = (repo / "index.html").read_text(encoding="utf-8").replace(old, new)
    assert apply_patch.apply(_diff(repo, old, new), repo) == ["index.html"]
    assert (repo / "index.html").read_text(encoding="utf-8") == expected


def test_apply_refuses_mismatched_context(tmp_path):
    repo = tmp_path / "app"
    shutil.copytree(PILOT / "app", repo)
    diff = _diff(repo, "rs-pilot-event-assets-2025", "x-bucket-name")
    (repo / "index.html").write_text("something else entirely\n", encoding="utf-8")
    with pytest.raises(apply_patch.PatchError):
        apply_patch.apply(diff, repo)


def test_apply_refuses_path_escape(tmp_path):
    with pytest.raises(apply_patch.PatchError):
        apply_patch.apply("--- a/../x\n+++ b/../x\n@@ -1 +1 @@\n-a\n+b\n", tmp_path)
