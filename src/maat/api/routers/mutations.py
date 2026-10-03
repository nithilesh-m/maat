from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError

from maat import service
from maat.api.auth import Role, User, require
from maat.api.events import EventLog
from maat.api.routers.evidence import records, run_dir, sealed
from maat.catalog.c2at import VersionMismatchError
from maat.catalog.delta import delta_summary, delta_view, utility_summary
from maat.catalog.loader import load_catalog
from maat.evidence.bundle import BUNDLE_FILE, read_bundle
from maat.evidence.signing import RunKey
from maat.gates.engine import policy_bundle_version
from maat.profile.loader import ProfileError, load_profile
from maat.remediation.apply import SandboxError
from maat.review.queue import (
    ReviewInputError,
    Waiver,
    add_waiver,
    pending_reviews,
    record_human_decision,
)
from maat.schemas.evidence import EvidenceType

router = APIRouter()


def reviewer_key(request: Request) -> RunKey:
    p = Path(request.app.state.settings.reviewer_key)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        RunKey.generate().save_pem(p)
        p.chmod(0o600)
    return RunKey.load_pem(p)


def _events(request: Request, run_id: str) -> EventLog:
    return EventLog(request.app.state.worker.events_dir(run_id))


class ReviewIn(BaseModel):
    clause_id: str
    label: Literal["S", "P", "N", "NA"]
    rationale: str


class ApplyIn(BaseModel):
    mitigation_ids: list[str]


@router.get("/review-queue", dependencies=[require(Role.viewer)])
def review_queue(request: Request) -> list[dict]:
    out = []
    for row in request.app.state.store.list(limit=500):
        d = Path(row["run_dir"])
        if not (d / BUNDLE_FILE).exists():
            continue
        try:
            pending = pending_reviews(d)
        except (ValueError, FileNotFoundError):
            continue
        out += [
            {
                "run_id": row["run_id"],
                "clause_id": p.clause_id,
                "judges": [j.model_dump(mode="json") for j in p.judges],
                "rationale": p.rationale,
            }
            for p in pending
        ]
    return out


@router.post("/runs/{run_id}/reviews")
def review(
    run_id: str, body: ReviewIn, request: Request, user: User = require(Role.reviewer)
) -> dict:
    d = run_dir(request, run_id)
    try:
        b = record_human_decision(
            d,
            body.clause_id,
            body.label,
            user.name,
            body.rationale,
            reviewer_key(request),
            datetime.now(UTC),
        )
    except ReviewInputError as e:
        raise HTTPException(422, str(e)) from e
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(409, str(e)) from e
    _events(request, run_id).append(
        "review_recorded", {"clause_id": body.clause_id, "label": body.label, "by": user.name}
    )
    return {"bundle_id": b.header.bundle_id, "revision": b.header.revision, "status": b.status}


@router.post("/runs/{run_id}/waivers")
def waive(run_id: str, body: Waiver, request: Request, user: User = require(Role.reviewer)) -> dict:
    d = run_dir(request, run_id)
    try:
        b = add_waiver(d, body, reviewer_key(request), datetime.now(UTC))
    except ReviewInputError as e:
        raise HTTPException(422, str(e)) from e
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(409, str(e)) from e
    _events(request, run_id).append(
        "waiver_added", {"waiver_id": body.id, "clause_id": body.clause_id, "by": user.name}
    )
    return {"bundle_id": b.header.bundle_id, "revision": b.header.revision, "status": b.status}


@router.get("/waivers", dependencies=[require(Role.viewer)])
def list_waivers(request: Request) -> list[dict]:
    out = []
    for row in request.app.state.store.list(limit=500):
        d = Path(row["run_dir"])
        if not (d / "ledger.sqlite").exists():
            continue
        try:
            recs = records(d)
        except sqlite3.DatabaseError:
            continue
        out += [
            {"run_id": row["run_id"], "record_id": r.id, "waiver": r.result["waiver"]}
            for r in recs
            if r.evidence_type is EvidenceType.WAIVER and "waiver" in r.result
        ]
    return out


def _profile(d: Path):
    p = d / "profile.yaml"
    if not p.exists():
        raise HTTPException(409, "run has no stored profile.yaml (is it finished?)")
    try:
        return load_profile(p)
    except ProfileError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/runs/{run_id}/mitigations", dependencies=[require(Role.viewer)])
def mitigations(run_id: str, request: Request) -> dict:
    d, _b = sealed(request, run_id)
    plans, manual = service.propose(d, _profile(d))
    return {"plans": [p.model_dump(mode="json") for p in plans], "manual": manual}


@router.post("/runs/{run_id}/mitigations/apply", status_code=202)
def apply_mitigations(
    run_id: str, body: ApplyIn, request: Request, user: User = require(Role.admin)
) -> dict:
    d, _b = sealed(request, run_id)
    prof = _profile(d)
    if not prof.sandbox_allowed:
        raise HTTPException(
            403,
            str(
                SandboxError("profile.sandbox_allowed must be true to apply mitigations (sandbox)")
            ),
        )
    _events(request, run_id).append(
        "remediation_started", {"mitigation_ids": body.mitigation_ids, "by": user.name}
    )
    request.app.state.worker.submit_remediation(run_id, body.mitigation_ids, reviewer_key(request))
    return {"run_id": run_id, "status": "remediating"}


@router.get("/runs/{run_id}/children", dependencies=[require(Role.viewer)])
def children(run_id: str, request: Request) -> list[str]:
    d = run_dir(request, run_id)
    root = d / "children"
    if not root.exists():
        return []
    return sorted(c.name for c in root.iterdir() if c.is_dir() and (c / BUNDLE_FILE).exists())


@router.get("/runs/{run_id}/delta/{child_id}", dependencies=[require(Role.viewer)])
def delta(run_id: str, child_id: str, request: Request, regime: str = "EU") -> dict:
    d, parent = sealed(request, run_id)
    child_dir = d / "children" / child_id
    if "/" in child_id or not (child_dir / BUNDLE_FILE).exists():
        raise HTTPException(404, f"child run {child_id} not found")
    try:
        child = read_bundle(child_dir)
        rows = delta_view(parent, child, load_catalog(), regime, policy_bundle_version())
    except (VersionMismatchError, ValidationError, ValueError) as e:
        raise HTTPException(409, str(e)) from e
    return {"rows": rows, "summary": {**delta_summary(rows), **utility_summary(child_dir)}}
