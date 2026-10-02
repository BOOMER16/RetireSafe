"""REST API (FastAPI).

POST /v1/assessments      multipart: plan, dns[], logs[], repo (zip / tar.gz), config (JSON string)
GET  /v1/assessments      recent assessments
GET  /v1/assessments/{id} full evidence record
GET  /v1/assessments/{id}/report.md
POST /v1/drift-scans      {"hostnames": [...]}  live read-only DNS/S3 checks (names you own)
GET  /v1/drift-scans/{id}
GET  /v1/knowledge        rule set, coverage and source register
POST /v1/demo/pilot       import the recorded pilot run (pilot/results) when running from a checkout
GET  /healthz
GET  /                    web console (static files in retiresafe/web, no third-party requests)

Set RETIRESAFE_API_KEY to require an ``X-API-Key`` header on /v1 routes.
"""
from __future__ import annotations

import hmac
import json
import os
import shutil
import tarfile
import tempfile
import uuid
import zipfile
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__, ownership
from ..paths import REPO_ROOT
from ..config import log_from, parse_as_of, policy_dict, policy_from
from ..engine.assess import AssessmentInput, run
from ..knowledge import providers
from ..knowledge.fingerprints import CATALOGUE_COMMIT
from ..knowledge.sources import SOURCES
from ..report import evidence
from .store import Store

MAX_UPLOAD = int(os.environ.get("RETIRESAFE_MAX_UPLOAD_MB", "512")) * 1024 * 1024
MAX_EXTRACT = int(os.environ.get("RETIRESAFE_MAX_EXTRACT_MB", "2048")) * 1024 * 1024
MAX_MEMBERS = int(os.environ.get("RETIRESAFE_MAX_ARCHIVE_FILES", "100000"))
MAX_SCAN_NAMES = 2000
WEB_DIR = Path(__file__).resolve().parents[1] / "web"
PILOT_RESULTS = REPO_ROOT / "pilot" / "results"
PILOT_RUNS = ("before_strict", "before_balanced", "after_strict")
# The console loads nothing from third parties and runs no inline script or style.
UI_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
          "connect-src 'self'; font-src 'self'; manifest-src 'self'; base-uri 'none'; "
          "form-action 'none'; frame-ancestors 'none'")

app = FastAPI(title="RetireSafe", version=__version__,
              description="Evidence-driven pre-flight checks for retiring cloud resources")
_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def auth(x_api_key: str | None = Header(default=None)) -> None:
    key = os.environ.get("RETIRESAFE_API_KEY")
    if key and not hmac.compare_digest((x_api_key or "").encode(), key.encode()):
        raise HTTPException(401, "missing or invalid X-API-Key")


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/v1"):
        resp.headers["Cache-Control"] = "no-store"        # evidence records should not sit in caches
    if request.url.path == "/" or request.url.path.startswith("/ui"):
        resp.headers["Content-Security-Policy"] = UI_CSP
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Cache-Control"] = "no-cache"
    return resp


async def _save(up: UploadFile, dest: Path) -> Path:
    name = Path(up.filename or "upload").name
    if not name or name in (".", ".."):
        raise HTTPException(400, "invalid file name")
    target = dest / name
    size = 0
    with open(target, "wb") as f:
        while chunk := await up.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(413, f"{name} exceeds the upload limit")
            f.write(chunk)
    return target


def _safe_extract(archive: Path, dest: Path) -> None:
    dest = dest.resolve()

    def check(member: str) -> None:
        p = (dest / member).resolve()
        if dest != p and dest not in p.parents:
            raise HTTPException(400, f"archive member escapes the extraction directory: {member}")
    def limits(sizes: list[int]) -> None:
        if len(sizes) > MAX_MEMBERS:
            raise HTTPException(413, f"archive has {len(sizes)} files; limit {MAX_MEMBERS}")
        if sum(sizes) > MAX_EXTRACT:
            raise HTTPException(413, f"archive expands to {sum(sizes) // 2**20} MB; limit {MAX_EXTRACT // 2**20} MB")
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            limits([i.file_size for i in infos])             # declared sizes; checked again while writing
            for m in z.namelist():
                check(m)
            budget = MAX_EXTRACT
            for info in infos:
                if info.is_dir():
                    continue
                target = dest / info.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(target, "wb") as out:
                    while chunk := src.read(1 << 20):
                        budget -= len(chunk)
                        if budget < 0:
                            raise HTTPException(413, "archive expands beyond the extraction limit")
                        out.write(chunk)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as t:
            members = t.getmembers()
            limits([m.size for m in members])
            for m in members:
                check(m.name)
                if m.issym() or m.islnk() or m.isdev():
                    raise HTTPException(400, f"links and devices are not allowed in the archive: {m.name}")
            t.extractall(dest, filter="data")
    else:
        raise HTTPException(400, "repo must be a .zip or .tar(.gz) archive")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/v1/knowledge", dependencies=[Depends(auth)])
def knowledge() -> dict:
    return {"rules_version": providers.RULES_VERSION, "fingerprint_catalogue_commit": CATALOGUE_COMMIT,
            "name_bearing_resource_types": sorted(providers.NAME_BEARING), "sources": SOURCES,
            "owned_domains": ownership.owned_domains(),
            "pilot_available": all((PILOT_RESULTS / f"{t}.json").is_file() for t in PILOT_RUNS)}


@app.post("/v1/demo/pilot", dependencies=[Depends(auth)])
def import_pilot() -> dict:
    """Load the recorded pilot assessments (real engine output, see pilot/README.md) into the store.

    Records are stored unchanged; importing twice is a no-op."""
    out = {}
    for tag in PILOT_RUNS:
        f = PILOT_RESULTS / f"{tag}.json"
        if not f.is_file():
            raise HTTPException(404, f"pilot results not found ({f.name}); run pilot/scripts/run_pilot.py "
                                     "from a repository checkout")
        rec = json.loads(f.read_text(encoding="utf-8"))
        if rec.get("schema") != "retiresafe.evidence/v1":
            raise HTTPException(422, f"{f.name} is not a retiresafe.evidence/v1 record")
        if not store().get_assessment(rec["assessment_id"]):
            store().put_assessment(rec)
        out[tag] = rec["assessment_id"]
    return {"imported": out, "source": "pilot/results"}


@app.post("/v1/assessments", dependencies=[Depends(auth)])
async def create_assessment(plan: UploadFile = File(...), dns: list[UploadFile] = File(default=[]),
                            logs: list[UploadFile] = File(default=[]), repo: UploadFile | None = File(default=None),
                            config: str = Form(default="{}")) -> dict:
    try:
        cfg = json.loads(config)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"config is not valid JSON: {e}") from e
    work = Path(tempfile.mkdtemp(prefix="retiresafe-"))
    try:
        plan_p = await _save(plan, work)
        dns_paths = []
        for d in dns:
            p = await _save(d, work)
            dns_paths.append((str(p), cfg.get("dns_origins", {}).get(p.name)))
        log_cfg = {c["filename"]: c for c in cfg.get("logs", [])}
        log_inputs = []
        for lg in logs:
            p = await _save(lg, work)
            if p.name not in log_cfg:
                raise HTTPException(400, f"config.logs has no entry for uploaded log {p.name}")
            log_inputs.append(log_from(log_cfg[p.name], str(p)))
        repos = {}
        if repo is not None:
            arc = await _save(repo, work)
            root = work / "repo"
            root.mkdir()
            _safe_extract(arc, root)
            repos[cfg.get("repo_label", Path(repo.filename or "repo").stem)] = str(root)
        policy = policy_from(cfg.get("policy"))
        inp = AssessmentInput(str(plan_p), dns_paths, repos, log_inputs, policy, parse_as_of(cfg.get("as_of")),
                              cfg.get("migrate_to", {}), None, cfg.get("waivers", []))
        result = run(inp)
        rec = evidence.record(result, policy_dict(policy))
        store().put_assessment(rec)
        return rec
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        shutil.rmtree(work, ignore_errors=True)


@app.get("/v1/assessments", dependencies=[Depends(auth)])
def list_assessments(limit: int = 50) -> list[dict]:
    return store().list_assessments(min(max(limit, 1), 500))


@app.get("/v1/assessments/{aid}", dependencies=[Depends(auth)])
def get_assessment(aid: str) -> dict:
    rec = store().get_assessment(aid)
    if not rec:
        raise HTTPException(404, "assessment not found")
    return rec


@app.get("/v1/assessments/{aid}/report.md", response_class=PlainTextResponse, dependencies=[Depends(auth)])
def get_report(aid: str) -> str:
    return evidence.markdown(get_assessment(aid))


class ScanRequest(BaseModel):
    hostnames: list[str] = Field(..., min_length=1, max_length=MAX_SCAN_NAMES)


@app.post("/v1/drift-scans", dependencies=[Depends(auth)])
def create_scan(req: ScanRequest) -> dict:
    from ..probes import live
    domains = ownership.owned_domains()
    if not domains:
        raise HTTPException(403, "live scans are disabled until RETIRESAFE_OWNED_DOMAINS lists the domains "
                                 "your organisation owns (only scan names you own)")
    ok, refused = ownership.split(req.hostnames, domains)
    if not ok:
        raise HTTPException(422, f"none of the hostnames are under the owned domains {domains}")
    findings = [asdict(f) for f in live.scan(ok)]
    rec = store().put_scan(str(uuid.uuid4()), findings)
    rec["refused_not_owned"] = refused
    return rec


@app.delete("/v1/assessments/{aid}", dependencies=[Depends(auth)])
def delete_assessment(aid: str) -> dict:
    if not store().delete("assessments", aid):
        raise HTTPException(404, "assessment not found")
    return {"deleted": aid}


@app.delete("/v1/drift-scans/{sid}", dependencies=[Depends(auth)])
def delete_scan(sid: str) -> dict:
    if not store().delete("drift_scans", sid):
        raise HTTPException(404, "scan not found")
    return {"deleted": sid}


@app.get("/v1/drift-scans/{sid}", dependencies=[Depends(auth)])
def get_scan(sid: str) -> dict:
    rec = store().get_scan(sid)
    if not rec:
        raise HTTPException(404, "scan not found")
    return rec


@app.get("/", include_in_schema=False)
def console() -> RedirectResponse:
    return RedirectResponse("/ui/")


if WEB_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=WEB_DIR, html=True), name="ui")
