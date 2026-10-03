from __future__ import annotations

import re
import sqlite3
import tempfile
import zipfile
import zlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from maat.api.auth import Role, User, require
from maat.catalog.c2at import VersionMismatchError, render_view
from maat.catalog.loader import load_catalog
from maat.catalog.metrics import (
    adequacy_score,
    clause_coverage,
    dimension_scores,
    measured_evidence_ratio,
)
from maat.evidence.bundle import BUNDLE_FILE, read_bundle
from maat.evidence.verify import verify_run
from maat.gates.engine import policy_bundle_version
from maat.report.render import render_html, render_pdf, report_context
from maat.schemas.evidence import EvidenceRecord

router = APIRouter()

MAX_UNZIPPED_BYTES = 256 * 1024 * 1024
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
DIGEST = re.compile(r"^(sha256:)?[0-9a-f]{64}$")


def run_dir(request: Request, run_id: str) -> Path:
    row = request.app.state.store.get(run_id)
    if row is None:
        raise HTTPException(404, f"unknown run {run_id}")
    return Path(row["run_dir"])


def sealed(request: Request, run_id: str):
    d = run_dir(request, run_id)
    if not (d / BUNDLE_FILE).exists():
        raise HTTPException(409, "run not sealed yet")
    return d, read_bundle(d)


def records(d: Path) -> list[EvidenceRecord]:
    conn = sqlite3.connect(f"file:{d / 'ledger.sqlite'}?mode=ro", uri=True)
    try:
        return [
            EvidenceRecord.model_validate_json(b)
            for (b,) in conn.execute("SELECT body FROM evidence ORDER BY seq")
        ]
    finally:
        conn.close()


@router.get("/runs/{run_id}/views/{regime}")
def view(run_id: str, regime: str, request: Request, _: User = require(Role.viewer)) -> dict:
    d, b = sealed(request, run_id)
    try:
        rows = render_view(b, load_catalog(), regime, policy_bundle_version())
    except VersionMismatchError as e:
        raise HTTPException(409, str(e)) from e
    return {
        "rows": [r.model_dump(mode="json") for r in rows],
        "cc": clause_coverage(rows),
        "as": adequacy_score(rows),
        "mer": measured_evidence_ratio(rows, b.entries),
    }


@router.get("/artifacts/{run_id}/{sha}")
def artifact(
    run_id: str,
    sha: str,
    request: Request,
    include_sensitive: bool = False,
    user: User = require(Role.viewer),
) -> Response:
    if not DIGEST.fullmatch(sha):
        raise HTTPException(400, "artifact id must be a sha256 digest")
    sha = "sha256:" + sha.removeprefix("sha256:")  # one canonical form for every comparison
    d = run_dir(request, run_id)
    if not (d / "ledger.sqlite").exists():
        raise HTTPException(409, "run has no ledger yet")
    sensitive = any(a.sha256 == sha and a.sensitive for r in records(d) for a in r.artifacts)
    if sensitive and (not include_sensitive or user.role < Role.reviewer):
        raise HTTPException(
            403, "sensitive artifact: reviewer role and include_sensitive=true required"
        )
    p = d / "artifacts" / sha.removeprefix("sha256:")
    if not p.is_file():
        raise HTTPException(404, "artifact not found")
    return Response(p.read_bytes(), media_type="application/octet-stream")


@router.post("/verify")
async def verify_upload(file: UploadFile, _: User = require(Role.viewer)) -> dict:
    with tempfile.TemporaryDirectory() as td:
        zp = Path(td) / "u.zip"
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"upload exceeds {MAX_UPLOAD_BYTES} bytes")
        zp.write_bytes(data)
        out = Path(td) / "run"
        try:
            z = zipfile.ZipFile(zp)
        except zipfile.BadZipFile:
            raise HTTPException(400, "not a valid zip archive") from None
        with z:
            for n in z.namelist():
                if not (out / n).resolve().is_relative_to(out.resolve()) or n.startswith("/"):
                    raise HTTPException(400, "unsafe path in zip")
            if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED_BYTES:
                raise HTTPException(400, "archive too large")
            try:
                z.extractall(out)
            except (zipfile.BadZipFile, zlib.error, OSError, RuntimeError) as e:
                raise HTTPException(400, f"corrupt archive: {type(e).__name__}") from None
        # Zipping a run folder nests it under one top-level directory; accept that layout.
        if not (out / "bundle.dsse.json").exists():
            entries = [e for e in out.iterdir() if e.name != "__MACOSX"]
            if len(entries) == 1 and entries[0].is_dir():
                out = entries[0]
        rep = verify_run(out)
        return {
            "ok": rep.ok,
            "problems": rep.problems,
            "bundle_id": rep.bundle_id,
            "records": rep.records,
        }


@router.get("/runs/{run_id}/records")
def list_records(
    run_id: str,
    request: Request,
    type: str | None = None,
    agent: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=1_000_000),
    _: User = require(Role.viewer),
) -> list[dict]:
    d = run_dir(request, run_id)
    if not (d / "ledger.sqlite").exists():
        raise HTTPException(409, "run has no ledger yet")
    rows = [
        r
        for r in records(d)
        if (type is None or r.evidence_type.value == type) and (agent is None or r.agent == agent)
    ]
    return [r.model_dump(mode="json") for r in rows[offset : offset + limit]]


@router.get("/records/{run_id}/{record_id}")
def get_record(
    run_id: str, record_id: str, request: Request, _: User = require(Role.viewer)
) -> dict:
    for r in records(run_dir(request, run_id)):
        if r.id == record_id:
            return r.model_dump(mode="json")
    raise HTTPException(404, f"record {record_id} not found in {run_id}")


@router.get("/runs/{run_id}/findings")
def findings(run_id: str, request: Request, _: User = require(Role.viewer)) -> list[dict]:
    _, b = sealed(request, run_id)
    return [f.model_dump(mode="json") for f in b.findings]


@router.get("/runs/{run_id}/decisions")
def decisions(run_id: str, request: Request, _: User = require(Role.viewer)) -> list[dict]:
    _, b = sealed(request, run_id)
    return [d.model_dump(mode="json") for d in b.decisions]


@router.get("/runs/{run_id}/scores")
def scores(run_id: str, request: Request, _: User = require(Role.viewer)) -> dict:
    d, b = sealed(request, run_id)
    catalog = load_catalog()
    out, all_rows = {}, []
    try:
        for reg in b.header.regimes:
            rows = render_view(b, catalog, reg, policy_bundle_version())
            all_rows += rows
            out[reg] = {
                "cc": clause_coverage(rows),
                "as": adequacy_score(rows),
                "mer": measured_evidence_ratio(rows, b.entries),
            }
    except VersionMismatchError as e:
        raise HTTPException(409, str(e)) from e
    return {"regimes": out, "dimensions": dimension_scores(all_rows, catalog)}


@router.get("/runs/{run_id}/bundle")
def bundle(run_id: str, request: Request, _: User = require(Role.viewer)) -> Response:
    d, _b = sealed(request, run_id)
    return Response((d / BUNDLE_FILE).read_bytes(), media_type="application/json")


@router.get("/runs/{run_id}/verify")
def verify_stored(run_id: str, request: Request, _: User = require(Role.viewer)) -> dict:
    rep = verify_run(run_dir(request, run_id))
    return {
        "ok": rep.ok,
        "problems": rep.problems,
        "bundle_id": rep.bundle_id,
        "records": rep.records,
    }


def _report_html(request: Request, run_id: str) -> str:
    d, _b = sealed(request, run_id)
    try:
        return render_html(report_context(d, load_catalog(), policy_bundle_version()))
    except VersionMismatchError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/runs/{run_id}/report.html")
def report_html(run_id: str, request: Request, _: User = require(Role.viewer)) -> HTMLResponse:
    return HTMLResponse(_report_html(request, run_id))


@router.get("/runs/{run_id}/report.pdf")
def report_pdf(run_id: str, request: Request, _: User = require(Role.viewer)) -> Response:
    html = _report_html(request, run_id)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "report.pdf"
        try:
            render_pdf(html, out)
        except OSError as e:
            raise HTTPException(501, f"PDF rendering unavailable (pango missing?): {e}") from e
        return Response(out.read_bytes(), media_type="application/pdf")
