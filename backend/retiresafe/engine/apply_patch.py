"""Apply the unified diffs RetireSafe generates (pure Python, no `git` needed).

Every context and removed line is checked against the target file; a mismatch raises
instead of guessing, so a patch never lands on code it was not generated from.
"""
from __future__ import annotations

import re
from pathlib import Path

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchError(ValueError):
    pass


def _split_files(diff: str) -> list[tuple[str, list[str]]]:
    files, cur, lines = [], None, []
    for ln in diff.splitlines(keepends=True):
        if ln.startswith("--- "):
            if cur:
                files.append((cur, lines))
            cur, lines = None, []
        elif ln.startswith("+++ ") and cur is None:
            path = ln[4:].strip()
            cur = path[2:] if path.startswith(("a/", "b/")) else path
        elif cur is not None:
            lines.append(ln)
    if cur:
        files.append((cur, lines))
    return files


def apply(diff: str, root: str | Path) -> list[str]:
    """Apply ``diff`` to files under ``root``. Returns the relative paths changed."""
    root = Path(root)
    changed = []
    for rel, body in _split_files(diff):
        target = (root / rel).resolve()
        if root.resolve() not in target.parents:
            raise PatchError(f"patch path escapes the target directory: {rel}")
        old = target.read_text(encoding="utf-8").splitlines(keepends=True)
        new, pos, i = [], 0, 0
        while i < len(body):
            m = HUNK.match(body[i])
            if not m:
                i += 1
                continue
            start = int(m.group(1)) - 1
            new.extend(old[pos:start])
            pos = start
            i += 1
            while i < len(body) and not body[i].startswith("@@"):
                tag, text = body[i][:1], body[i][1:]
                if tag in (" ", "-"):
                    if pos >= len(old) or old[pos].rstrip("\r\n") != text.rstrip("\r\n"):
                        raise PatchError(f"{rel}: context mismatch at line {pos + 1}")
                    if tag == " ":
                        new.append(old[pos])
                    pos += 1
                elif tag == "+":
                    new.append(text)
                i += 1
        new.extend(old[pos:])
        target.write_text("".join(new), encoding="utf-8", newline="")
        changed.append(rel)
    return changed
