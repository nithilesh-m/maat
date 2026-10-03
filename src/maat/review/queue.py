from __future__ import annotations

import fcntl
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from pydantic import AwareDatetime, BaseModel

from maat.catalog.loader import load_catalog
from maat.evidence.bundle import build_bundle, read_bundle, write_bundle
from maat.evidence.ledger import Ledger
from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from maat.gates.engine import OpaEngine
from maat.runner import clause_ids_by_tool, waivers_from
from maat.schemas.bundle import AuditBundle
from maat.schemas.decisions import GateDecision, GateOutcome
from maat.schemas.evidence import EvidenceDraft, EvidenceRecord, EvidenceType

LABEL_OUTCOME = {
    "S": GateOutcome.PASS,
    "P": GateOutcome.PASS,
    "N": GateOutcome.FAIL,
    "NA": GateOutcome.NOT_APPLICABLE,
}


class Waiver(BaseModel):
    id: str
    clause_id: str
    owner: str
    scope: str
    expiry: AwareDatetime
    compensations: list[str]


def pending_reviews(run_dir: Path) -> list[GateDecision]:
    return [d for d in read_bundle(run_dir).decisions if d.outcome is GateOutcome.ABSTAIN]


def _reseal(
    run_dir: Path, old: AuditBundle, ledger: Ledger, decisions: list[GateDecision], signer: RunKey
) -> AuditBundle:
    cat = load_catalog()
    controls = [cat.controls[d.clause_id] for d in decisions if d.clause_id in cat.controls]
    status = (
        "pending_review" if any(d.outcome is GateOutcome.ABSTAIN for d in decisions) else "complete"
    )
    h = old.header
    b = build_bundle(
        run_id=h.run_id,
        target_ref=h.target_ref,
        tier=h.tier.value,
        regimes=h.regimes,
        versions=h.versions,
        created_at=h.created_at,
        records=ledger.records(),
        decisions=decisions,
        clause_ids_by_tool=clause_ids_by_tool(controls),
        findings=old.findings,
        status=status,
        revision=h.revision + 1,
        previous_bundle_id=h.bundle_id,
        parent_bundle_id=h.parent_bundle_id,
    )
    write_bundle(b, run_dir, signer)
    return b


class ReviewInputError(ValueError):
    """The requested review or waiver is not allowed for this run (a client error)."""


_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_GUARD = threading.Lock()


@contextmanager
def run_lock(run_dir: Path):
    """Serialise mutations of one run across threads and processes (flock on `.maat.lock`)."""
    key = str(Path(run_dir).resolve())
    with _THREAD_GUARD:
        tlock = _THREAD_LOCKS.setdefault(key, threading.Lock())
    with tlock:
        lock_path = Path(run_dir) / ".maat.lock"
        with lock_path.open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def _open(run_dir: Path, signer: RunKey) -> tuple[AuditBundle, Ledger]:
    rep = verify_run(run_dir)
    if not rep.ok:
        raise ValueError(f"run does not verify; refusing to build on it: {rep.problems}")
    old = read_bundle(run_dir)
    return old, Ledger(Path(run_dir) / "ledger.sqlite", old.header.run_id, signer)


def _append(ledger: Ledger, old: AuditBundle, etype, tool, params, result, now) -> EvidenceRecord:
    return ledger.append(
        EvidenceDraft(
            run_id=old.header.run_id,
            agent="human",
            tool=tool,
            evidence_type=etype,
            target_ref=old.header.target_ref,
            params=params,
            result=result,
            started_at=now,
            ended_at=now,
        )
    )


def record_human_decision(
    run_dir: Path,
    clause_id: str,
    label: str,
    reviewer: str,
    rationale: str,
    signer: RunKey,
    now: datetime,
) -> AuditBundle:
    """Resolve an abstained control. Only abstentions go to human review: a measured decision
    (for example a non-waivable block) can never be overturned by a verdict."""
    with run_lock(run_dir):
        old, ledger = _open(run_dir, signer)
        try:
            target = next((d for d in old.decisions if d.clause_id == clause_id), None)
            if target is None:
                raise ReviewInputError(f"control {clause_id} is not in this bundle")
            if target.outcome is not GateOutcome.ABSTAIN:
                raise ReviewInputError(
                    f"{clause_id} is {target.outcome.value}, not abstain; "
                    "only abstained controls go to human review"
                )
            rec = _append(
                ledger,
                old,
                EvidenceType.HUMAN_DECISION,
                "human_review",
                {"control_id": clause_id},
                {"label": label, "reviewer": reviewer, "rationale": rationale},
                now,
            )
            decisions = [
                d
                if d.clause_id != clause_id
                else GateDecision(
                    clause_id=clause_id,
                    gate=d.gate,
                    method="human",
                    policy_version=d.policy_version,
                    inputs=[*d.inputs, rec.id],
                    outcome=LABEL_OUTCOME[label],
                    partial=label == "P",
                    rationale=f"{reviewer}: {rationale}",
                    judges=d.judges,
                )
                for d in old.decisions
            ]
            return _reseal(run_dir, old, ledger, decisions, signer)
        finally:
            ledger.close()


def add_waiver(run_dir: Path, waiver: Waiver, signer: RunKey, now: datetime) -> AuditBundle:
    with run_lock(run_dir):
        old, ledger = _open(run_dir, signer)
        try:
            cat = load_catalog()
            ctrl = cat.controls.get(waiver.clause_id)
            if ctrl is None or waiver.clause_id not in {d.clause_id for d in old.decisions}:
                raise ReviewInputError(f"control {waiver.clause_id} is not in this bundle")
            if ctrl.predicate is None:
                raise ReviewInputError(
                    f"{waiver.clause_id} is a qualitative control; waivers apply to quantitative "
                    "gates (use a human review instead)"
                )
            w = waiver.model_dump(mode="json")
            _append(
                ledger,
                old,
                EvidenceType.WAIVER,
                "waiver",
                {"control_id": waiver.clause_id},
                {"waiver": w},
                now,
            )
            records = ledger.records()
            latest = {}
            for r in records:
                if r.evidence_type is EvidenceType.MEASURED:
                    latest[r.tool.split("@", 1)[0]] = r
            ev = {e.tool: latest[e.tool] for e in ctrl.evidence_edges if e.tool in latest}
            new = OpaEngine().decide(ctrl, ev, old.header.tier, waivers_from(records), {}, now)
            decisions = [new if d.clause_id == waiver.clause_id else d for d in old.decisions]
            return _reseal(run_dir, old, ledger, decisions, signer)
        finally:
            ledger.close()
