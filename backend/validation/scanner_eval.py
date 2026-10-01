"""Measure the repository scanner on real open-source code.

Corpus (shallow clones, commit recorded in the output): allenai/allennlp, keras-team/keras,
tensorflow/datasets, mlflow/mlflow, apache/airflow, huggingface/transformers.

Phase A - collisions: pretend common words are retiring bucket names. These repos do not own
          buckets with those names, so a bare quoted-word match without S3 context is a false
          alarm. Compare literal_mode="any" (old behaviour) with "s3_context" (new default).
Phase B - real names: bucket names the repos really reference, found by an independent extractor
          (different regexes from the product), filtered by a fixed rule. Produces a random
          labelling sample of hits (precision) and of whole-word occurrences the scanner did not
          report (recall).

    python validation/scanner_eval.py /path/to/realrepos
"""
from __future__ import annotations

import collections
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from retiresafe.collectors import repo_scan  # noqa: E402

OUT = HERE / "results"
REPOS = ["allennlp", "keras", "datasets", "mlflow", "airflow", "transformers"]
GENERIC = ["data", "logs", "assets", "backup", "images", "static", "uploads", "models", "files", "archive",
           "artifacts", "cache", "output", "test"]
PLACEHOLDER = re.compile(r"bucket|test|^my|example|folder|output|blah|path|host|dag\d|team-|^some|^all-|start-|"
                         r"asset|archive|artifact|cache|dummy|^foo|^bar|^tmp|^temp|^data$|^name$|^prefix$")
IND = [re.compile(r"https?://([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])\.s3[a-z0-9.-]*\.amazonaws\.com", re.I),
       re.compile(r"https?://s3[a-z0-9.-]*\.amazonaws\.com/([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])/", re.I),
       re.compile(r"\bs3a?://([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])(?=[/'\"\s]|$)", re.I)]


def head(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()


def text_files(root: Path):
    for p in root.rglob("*"):
        if ".git" in p.parts or not p.is_file() or p.is_symlink() or p.stat().st_size > repo_scan.MAX_BYTES:
            continue
        raw = p.read_bytes()
        if b"\x00" in raw[:8192]:
            continue
        yield p, raw.decode("utf-8", errors="replace")


def independent_names(roots: list[Path]) -> collections.Counter:
    c = collections.Counter()
    for r in roots:
        for _, t in text_files(r):
            for rx in IND:
                for m in rx.finditer(t):
                    n = m.group(1).lower()
                    if not n.startswith("s3") and "amazonaws" not in n:
                        c[n] += 1
    return c


def phase_a(roots: list[Path]) -> dict:
    out = {}
    samples = []
    for mode in ("any", "bucket_position"):
        by = collections.Counter()
        for r in roots:
            hits, st = repo_scan.scan(r, set(GENERIC), set(), literal_mode="any" if mode == "any" else "s3_context")
            for h in hits:
                by[(h.method, h.context)] += 1
                if mode == "any" and h.method == "literal":
                    samples.append({"repo": r.name, "file": h.file, "line": h.line, "target": h.target,
                                    "text": h.text[:160]})
        out[mode] = {"total": sum(by.values()), "by_method": dict(collections.Counter(
            {m: sum(v for (mm, _), v in by.items() if mm == m) for m, _ in by})),
            "by_context": dict(collections.Counter({c: sum(v for (_, cc), v in by.items() if cc == c)
                                                     for _, c in by}))}
    blocking = []
    for r in roots:
        hits, _ = repo_scan.scan(r, set(GENERIC), set())
        blocking += [{"repo": r.name, "file": h.file, "line": h.line, "target": h.target, "method": h.method,
                      "context": h.context, "text": h.text[:160]} for h in hits
                     if h.method in ("url", "sdk_argument") and h.context != "comment"]
    random.Random(1).shuffle(samples)
    random.Random(3).shuffle(blocking)
    out["old_literal_sample"] = samples[:40]
    out["blocking_hits"] = len(blocking)
    out["blocking_sample"] = blocking[:40]
    return out


def phase_b(roots: list[Path], names: list[str]) -> dict:
    hits_all, occ_missed = [], []
    distinctive = [n for n in names if len(n) >= 8 and ("-" in n or "." in n)]
    word = re.compile(r"(?<![a-z0-9.-])(" + "|".join(re.escape(n) for n in distinctive) + r")(?![a-z0-9-])")
    for r in roots:
        hits, _ = repo_scan.scan(r, set(names), set())
        reported = {(h.file, h.line, h.target) for h in hits}
        hits_all += [{"repo": r.name, "file": h.file, "line": h.line, "target": h.target, "method": h.method,
                      "context": h.context, "text": h.text[:200]} for h in hits]
        for p, t in text_files(r):
            rel = p.relative_to(r).as_posix()
            for i, line in enumerate(t.splitlines(), 1):
                for m in word.finditer(line):
                    if (rel, i, m.group(1).lower()) not in reported:
                        occ_missed.append({"repo": r.name, "file": rel, "line": i, "target": m.group(1).lower(),
                                           "text": line.strip()[:200]})
    rng = random.Random(2)
    return {"names": names, "hits": len(hits_all),
            "hits_by_method": dict(collections.Counter(h["method"] for h in hits_all)),
            "hits_by_context": dict(collections.Counter(h["context"] for h in hits_all)),
            "unreported_whole_word_occurrences_distinctive": len(occ_missed),
            "distinctive_names": distinctive,
            "blocking_hits": sum(1 for h in hits_all if h["method"] in ("url", "sdk_argument")
                                 and h["context"] != "comment"),
            "precision_sample": rng.sample([h for h in hits_all if h["method"] in ("url", "sdk_argument")
                                            and h["context"] != "comment"], 60),
            "recall_sample": rng.sample(occ_missed, min(40, len(occ_missed)))}


def main() -> None:
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/user/realrepos")
    roots = [base / r for r in REPOS if (base / r).exists()]
    t0 = time.time()
    corpus = {r.name: head(r) for r in roots}
    cnt = independent_names(roots)
    names = sorted(n for n, k in cnt.items() if k >= 3 and not PLACEHOLDER.search(n))
    res = {"corpus_commits": corpus, "generic_names": GENERIC, "phase_a": phase_a(roots),
           "independent_names_found": len(cnt), "phase_b": phase_b(roots, names)}
    res["seconds"] = round(time.time() - t0)
    OUT.mkdir(exist_ok=True)
    (OUT / "scanner_eval_raw.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in res["phase_a"].items() if "sample" not in k}, indent=1))
    print("phase B names:", names)
    print({k: v for k, v in res["phase_b"].items() if "sample" not in k and k != "names"})


if __name__ == "__main__":
    main()
