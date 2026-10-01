"""Scanner rules derived from the real-repository evaluation (validation/scanner_eval_summary.json)."""
from retiresafe.collectors import repo_scan
from retiresafe.engine import decide
from retiresafe.models import ConditionResult, Reference, RefKind, Tri


def _scan(tmp_path, files: dict[str, str], buckets=("acme-data",)):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    hits, st = repo_scan.scan(tmp_path, set(buckets), set())
    return {(h.file, h.line): (h.method, h.context) for h in hits}, st


def test_bare_quoted_name_without_bucket_position_does_not_block(tmp_path):
    hits, st = _scan(tmp_path, {"a.py": 'task_id = "acme-data"\n', "b.py": 'import boto3\nx = "acme-data"\n'})
    assert ("a.py", 1) not in hits and st.literal_matches_discarded == 1     # no S3 context: discarded
    assert hits[("b.py", 2)][0] == "mention"                                  # S3 nearby: informational only


def test_bucket_position_blocks(tmp_path):
    hits, _ = _scan(tmp_path, {"c.py": 'import boto3\nS3_BUCKET = "acme-data"\ns3.download_file("acme-data", k, d)\n'})
    assert hits[("c.py", 2)][0] == hits[("c.py", 3)][0] == "sdk_argument"


def test_literals_are_case_sensitive(tmp_path):
    hits, _ = _scan(tmp_path, {"d.py": 'import boto3\nFILES = os.environ.get("FILES")\n'}, buckets=("files",))
    assert not hits


def test_gcs_bucket_argument_is_not_s3(tmp_path):
    hits, _ = _scan(tmp_path, {"providers/google/x.py": 'from google.cloud import storage\nhook.download(bucket_name="acme-data")\n'})
    assert hits[("providers/google/x.py", 2)][0] == "mention"


def test_prose_mention_and_contexts(tmp_path):
    hits, _ = _scan(tmp_path, {"docs/guide.md": "The files live in the acme-data S3 bucket.\n",
                               "tests/test_x.py": 'url = "https://acme-data.s3.amazonaws.com/x"\n',
                               "app.py": '# old: https://acme-data.s3.amazonaws.com/x\n',
                               "data/urls.txt": "https://acme-data.s3.amazonaws.com/y\n"})
    assert hits[("docs/guide.md", 1)] == ("mention", "docs")
    assert hits[("tests/test_x.py", 1)] == ("url", "test")
    assert hits[("app.py", 1)] == ("url", "comment")
    assert hits[("data/urls.txt", 1)] == ("url", "code")       # data files are read by code, not docs


def test_comment_and_mention_paths_cannot_block():
    T = ConditionResult(Tri.TRUE, "")
    c1 = ConditionResult(Tri.TRUE, "")
    for ref in (Reference("r", RefKind.CODE, "a:1", "", "acme-data", context="comment", method="url"),
                Reference("r", RefKind.CODE, "a:1", "", "acme-data", context="code", method="mention")):
        p = decide.evaluate_path(ref, c1, T, T)
        assert p.status == "safe" and p.broken_by == ["c4"]
