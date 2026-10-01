"""REST API (FastAPI).

POST /v1/assessments      multipart: plan, dns[], logs[], repo (zip / tar.gz), config (JSON string)
GET  /v1/assessments      recent assessments
GET  /v1/assessments/{id} full evidence record
GET  /v1/assessments/{id}/report.md
POST /v1/drift-scans      {"hostnames": [...]}  live read-only DNS/S3 checks (names you own)
GET  /v1/drift-scans/{id}
GET  /v1/knowledge        rule set, coverage and source register
GET  /healthz

Set RETIRESAFE_API_KEY to require an ``X-API-Key`` header on /v1 routes.
"""
from __future__ import annotations

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
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .. import __version__
from ..config import log_from, parse_as_of, policy_dict, policy_from
from ..engine.assess import AssessmentInput, run
from ..knowledge import providers
from ..knowledge.fingerprints import CATALOGUE_COMMIT
from ..knowledge.sources import SOURCES
from ..report import evidence
from .store import Store

MAX_UPLOAD = int(os.environ.get("RETIRESAFE_MAX_UPLOAD_MB", "512")) * 1024 * 1024
MAX_SCAN_NAMES = 2000

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
    if key and x_api_key != key:
        raise HTTPException(401, "missing or invalid X-API-Key")


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
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for m in z.namelist():
                check(m)
            z.extractall(dest)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as t:
            for m in t.getmembers():
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
            "name_bearing_resource_types": sorted(providers.NAME_BEARING), "sources": SOURCES}


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
                              cfg.get("migrate_to", {}))
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
    findings = [asdict(f) for f in live.scan(req.hostnames)]
    return store().put_scan(str(uuid.uuid4()), findings)


@app.get("/v1/drift-scans/{sid}", dependencies=[Depends(auth)])
def get_scan(sid: str) -> dict:
    rec = store().get_scan(sid)
    if not rec:
        raise HTTPException(404, "scan not found")
    return rec
