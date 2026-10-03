from __future__ import annotations

import asyncio
import json
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ulid import ULID

from maat.api.auth import Role, User, require
from maat.api.events import EventLog
from maat.api.policy import validate_profile_for_api
from maat.evidence.bundle import read_bundle
from maat.profile.loader import ProfileError, load_profile

router = APIRouter()

TERMINAL = ("complete", "failed", "paused")


class CreateRun(BaseModel):
    profile_yaml: str
    planner: Literal["agents", "static"] = "agents"
    auto_approve: bool = False


class Approval(BaseModel):
    approve_tier: bool
    ers: dict | None = None


def _row(request: Request, run_id: str) -> dict:
    row = request.app.state.store.get(run_id)
    if row is None:
        raise HTTPException(404, f"run {run_id} not found")
    return row


@router.get("/runs", dependencies=[require(Role.viewer)])
def list_runs(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[dict]:
    return request.app.state.store.list(limit, offset)


@router.post("/runs", status_code=202)
def create_run(body: CreateRun, request: Request, user: User = require(Role.reviewer)) -> dict:
    app = request.app
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "profile.yaml"
        tmp.write_text(body.profile_yaml, encoding="utf-8")
        try:
            prof = load_profile(tmp)
            validate_profile_for_api(prof, app.state.settings)
        except (ProfileError, ValueError) as e:
            raise HTTPException(422, str(e)) from None
    when = datetime.now(UTC)
    run_id = f"run-{when:%Y%m%d-%H%M%S}-{str(ULID())[-6:].lower()}"
    profiles = app.state.settings.runs_dir / "_profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    profile_path = profiles / f"{run_id}.yaml"
    profile_path.write_text(body.profile_yaml, encoding="utf-8")
    run_dir = app.state.settings.runs_dir / run_id
    app.state.store.create(run_id, run_dir, profile_path, body.planner, user.name)
    app.state.worker.submit(run_id, profile_path, body.planner, body.auto_approve)
    return {"run_id": run_id, "status": "queued"}


@router.get("/runs/{run_id}", dependencies=[require(Role.viewer)])
def get_run(run_id: str, request: Request) -> dict:
    row = _row(request, run_id)
    worker = request.app.state.worker
    out = dict(row)
    out["bundle_id"] = None
    if (Path(row["run_dir"]) / "bundle.dsse.json").exists():
        try:
            out["bundle_id"] = read_bundle(Path(row["run_dir"])).header.bundle_id
        except (ValueError, FileNotFoundError):
            pass
    approval = worker.approval_file(run_id)
    out["pending_approval"] = (
        json.loads(approval.read_text())
        if row["status"] == "paused" and approval.exists()
        else None
    )
    replay = worker.replay_file(run_id)
    out["replay"] = json.loads(replay.read_text()) if replay.exists() else None
    return out


@router.post("/runs/{run_id}/approval", status_code=202)
def approve(
    run_id: str, body: Approval, request: Request, _: User = require(Role.reviewer)
) -> dict:
    row = _row(request, run_id)
    if row["status"] != "paused":
        raise HTTPException(409, f"run is {row['status']}, not paused for approval")
    request.app.state.worker.submit(
        run_id,
        Path(row["profile"]),
        row["planner"],
        False,
        resume_answer=body.model_dump(),
        resume_existing=True,
    )
    return {"run_id": run_id, "status": "queued"}


@router.post("/runs/{run_id}/replay", status_code=202)
def replay(run_id: str, request: Request, _: User = require(Role.reviewer)) -> dict:
    row = _row(request, run_id)
    if row["status"] != "complete":
        raise HTTPException(409, f"only complete runs can be replayed (run is {row['status']})")
    request.app.state.worker.submit_replay(run_id)
    return {"run_id": run_id, "status": "replaying"}


KEEPALIVE_SECONDS = 15.0
POLL_SECONDS = 0.5


async def event_source(request: Request, store, log: EventLog, run_id: str, after: int):
    """Async so an idle stream parks on the event loop instead of holding a worker thread, and it
    stops as soon as the client disconnects."""
    seen = after
    last_sent = time.monotonic()
    while True:
        if await request.is_disconnected():
            return
        status = store.get(run_id)["status"]  # read status first: no event can be missed
        new = log.read(seen)
        for e in new:
            seen = e["seq"]
            yield f"id: {e['seq']}\nevent: {e['kind']}\ndata: {json.dumps(e['payload'])}\n\n"
            last_sent = time.monotonic()
        if not new and status in TERMINAL:
            return
        if time.monotonic() - last_sent >= KEEPALIVE_SECONDS:
            yield ": keep-alive\n\n"
            last_sent = time.monotonic()
        await asyncio.sleep(POLL_SECONDS)


@router.get("/runs/{run_id}/events", dependencies=[require(Role.viewer)])
def stream_events(run_id: str, request: Request) -> StreamingResponse:
    _row(request, run_id)
    store, worker = request.app.state.store, request.app.state.worker
    last = request.headers.get("Last-Event-ID")
    after = int(last) if last and last.lstrip("-").isdigit() else -1
    log = EventLog(worker.events_dir(run_id))
    return StreamingResponse(
        event_source(request, store, log, run_id, after), media_type="text/event-stream"
    )
