from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from maat import __version__
from maat.catalog.loader import applicable_controls
from maat.evidence.artifacts import ArtifactStore
from maat.evidence.bundle import build_bundle, write_bundle
from maat.evidence.ledger import Ledger
from maat.evidence.signing import RunKey
from maat.gates.engine import OpaEngine
from maat.schemas.bundle import AuditBundle
from maat.schemas.catalog import Catalog, Control
from maat.schemas.decisions import GateDecision, GateOutcome
from maat.schemas.evidence import EvidenceDraft, EvidenceRecord, EvidenceType
from maat.schemas.findings import Finding
from maat.schemas.profile import RiskTier, SystemProfile
from maat.targets.base import Target
from maat.tools import load_builtin_tools
from maat.tools.contract import ToolContext, utc_now
from maat.tools.registry import ToolRegistry, default_registry
from maat.tools.sweep import call_sweeping, sensitive_attributes_present, worst_for

Judge = Callable[[Control, dict[str, EvidenceRecord]], GateDecision]


class RunError(RuntimeError):
    pass


@dataclass
class RunConfig:
    run_id: str
    run_dir: Path
    signer: RunKey
    as_of: datetime
    clock: Callable[[], datetime] = utc_now
    id_factory: Callable[[], str] | None = None
    tool_params: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {"probe_prompt_injection": {"split": "dev"}}
    )
    overrides: dict[str, float] = field(default_factory=dict)
    on_event: Callable[[str, dict[str, Any]], None] | None = None
    services: Any = None
    replay: Any = None
    meta: dict[str, Any] = field(default_factory=dict)
    resume_existing: bool = False  # reopen a paused run instead of refusing an existing dir


@dataclass
class RunHandles:
    ledger: Ledger
    artifacts: ArtifactStore


def emit(config: RunConfig, kind: str, payload: dict[str, Any]) -> None:
    if config.on_event:
        config.on_event(kind, payload)


def open_run(config: RunConfig) -> RunHandles:
    run_dir = Path(config.run_dir)
    if config.resume_existing:
        if not (run_dir / "ledger.sqlite").exists():
            raise RunError(f"cannot resume: no ledger in {run_dir}")
    elif run_dir.exists():
        raise RunError(
            f"run directory already exists: {run_dir}; refusing to overwrite another run"
        )
    else:
        run_dir.mkdir(parents=True)
        if config.meta:
            (run_dir / "run_meta.json").write_text(json.dumps(config.meta, indent=2, default=str))
    return RunHandles(
        ledger=Ledger(run_dir / "ledger.sqlite", config.run_id, config.signer, config.id_factory),
        artifacts=ArtifactStore(run_dir / "artifacts", config.run_id),
    )


def tool_context(
    config: RunConfig, handles: RunHandles, agent: str, target: Target, profile: SystemProfile
) -> ToolContext:
    return ToolContext(
        run_id=config.run_id,
        agent=agent,
        target=target,
        ledger=handles.ledger,
        artifacts=handles.artifacts,
        profile=profile,
        clock=config.clock,
        services=config.services,
        replay=config.replay,
    )


def record_control_gap(
    control: Control, config: RunConfig, handles: RunHandles, target: Target, reason: str
) -> EvidenceRecord:
    t0 = config.clock()
    rec = handles.ledger.append(
        EvidenceDraft(
            run_id=config.run_id,
            agent=control.agent,
            tool="none",
            evidence_type=EvidenceType.GAP,
            target_ref=f"{target.target_id}@{target.version_hash}",
            params={"control_id": control.id},
            result={"error": reason},
            started_at=t0,
            ended_at=config.clock(),
        )
    )
    emit(config, "gap", {"control_id": control.id, "reason": reason, "record_id": rec.id})
    return rec


def derived_tool_params(profile: SystemProfile, target: Target) -> dict[str, dict[str, Any]]:
    """Defaults a static planner needs for tools with a required parameter."""
    data = getattr(target, "data", None)
    cols = set(getattr(data, "columns", []))
    attrs = [a for a in profile.sensitive_attributes if a in cols]
    if not attrs:
        return {}
    return {
        "tabular_group_metrics": {"attribute": attrs[0]},
        "find_proxy_features": {"attribute": attrs[0]},
    }


def effective_tool_params(
    profile: SystemProfile, target: Target, config: RunConfig
) -> dict[str, dict[str, Any]]:
    derived = derived_tool_params(profile, target)
    names = set(derived) | set(config.tool_params)
    return {n: {**derived.get(n, {}), **config.tool_params.get(n, {})} for n in names}


def collect_static_evidence(
    controls: list[Control],
    profile: SystemProfile,
    target: Target,
    config: RunConfig,
    handles: RunHandles,
    registry: ToolRegistry,
    candidates: dict[str, list[EvidenceRecord]] | None = None,
) -> dict[str, EvidenceRecord]:
    latest: dict[str, EvidenceRecord] = {}
    attrs = sensitive_attributes_present(profile, target)
    params = effective_tool_params(profile, target, config)
    for control in controls:
        specs = [s for s in (registry.get(e.tool) for e in control.evidence_edges) if s]
        if not specs:
            if control.manual_check:
                t0 = config.clock()
                handles.ledger.append(
                    EvidenceDraft(
                        run_id=config.run_id,
                        agent=control.agent,
                        tool="manual_check",
                        evidence_type=EvidenceType.MANUAL_NEEDED,
                        target_ref=f"{target.target_id}@{target.version_hash}",
                        params={"control_id": control.id},
                        result={"checklist": control.manual_check},
                        started_at=t0,
                        ended_at=config.clock(),
                    )
                )
            else:
                record_control_gap(
                    control, config, handles, target, "no registered tool can evidence this control"
                )
            continue
        for spec in specs:
            if spec.name in latest:
                continue
            emit(config, "tool_started", {"tool": spec.key, "agent": spec.agent})
            recs = call_sweeping(
                spec,
                lambda a=spec.agent: tool_context(config, handles, a, target, profile),
                params.get(spec.name, {}),
                attrs,
            )
            latest[spec.name] = recs[-1]
            if candidates is not None:
                candidates[spec.name] = recs
            for rec in recs:
                emit(
                    config,
                    "tool_finished",
                    {
                        "tool": rec.tool,
                        "record_id": rec.id,
                        "evidence_type": rec.evidence_type.value,
                    },
                )
    return latest


def waivers_from(records: Iterable[EvidenceRecord]) -> list[dict[str, Any]]:
    return [
        r.result["waiver"]
        for r in records
        if r.evidence_type is EvidenceType.WAIVER and "waiver" in r.result
    ]


def _record_judgment(
    ledger: Ledger, config: RunConfig, control: Control, d: GateDecision, target_ref: str
) -> None:
    """Judge-panel verdicts are LLM judgments: they belong in the signed ledger, not only in
    the (unsigned-by-Merkle) decision list."""
    t0 = config.clock()
    ledger.append(
        EvidenceDraft(
            run_id=config.run_id,
            agent="judge",
            tool="judge_panel",
            evidence_type=EvidenceType.LLM_JUDGMENT,
            target_ref=target_ref,
            params={"control_id": control.id},
            result={
                "outcome": d.outcome.value,
                "partial": d.partial,
                "agreement": d.agreement,
                "votes": [j.model_dump(mode="json") for j in d.judges],
            },
            started_at=t0,
            ended_at=config.clock(),
        )
    )


def gate_controls(
    controls: list[Control],
    evidence_by_tool: dict[str, EvidenceRecord],
    profile: SystemProfile,
    engine: OpaEngine,
    config: RunConfig,
    waivers: list[dict[str, Any]],
    judge: Judge | None = None,
    tier: RiskTier | None = None,
    candidates: dict[str, list[EvidenceRecord]] | None = None,
    ledger: Ledger | None = None,
    target_ref: str = "",
) -> list[GateDecision]:
    decisions = []
    for control in controls:
        ev = {
            e.tool: evidence_by_tool[e.tool]
            for e in control.evidence_edges
            if e.tool in evidence_by_tool
        }
        pred = control.predicate
        if candidates and pred is not None and len(candidates.get(pred.tool, [])) > 1:
            ev[pred.tool] = worst_for(control, candidates[pred.tool])
        if control.kind == "quantitative":
            d = engine.decide(
                control,
                ev,
                tier or profile.declared_risk_tier,
                waivers,
                config.overrides,
                config.as_of,
            )
        elif judge is not None:
            d = judge(control, ev)
            if ledger is not None and d.judges:
                _record_judgment(ledger, config, control, d, target_ref)
        else:
            d = GateDecision(
                clause_id=control.id,
                gate=control.gate,
                method="none",
                policy_version=engine.policy_version,
                inputs=sorted(r.id for r in ev.values()),
                outcome=GateOutcome.ABSTAIN,
                rationale="qualitative judging not configured",
            )
        decisions.append(d)
        emit(
            config,
            "gate_decision",
            {"control_id": d.clause_id, "outcome": d.outcome.value, "rationale": d.rationale},
        )
    return decisions


def clause_ids_by_tool(controls: list[Control]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = {}
    for c in controls:
        for e in c.evidence_edges:
            out.setdefault(e.tool, set()).add(c.id)
    return {k: sorted(v) for k, v in out.items()}


def seal_run(
    *,
    profile: SystemProfile,
    target: Target,
    catalog: Catalog,
    engine: OpaEngine,
    config: RunConfig,
    handles: RunHandles,
    controls: list[Control],
    decisions: list[GateDecision],
    registry: ToolRegistry,
    findings: Iterable[Finding] = (),
    status: str | None = None,
    parent_bundle_id: str | None = None,
) -> AuditBundle:
    records = handles.ledger.records()
    if status is None:
        status = (
            "pending_review"
            if any(d.outcome is GateOutcome.ABSTAIN for d in decisions)
            else "complete"
        )
    versions = {
        "maat": __version__,
        "catalog": catalog.version,
        "policies": engine.policy_version,
        **{f"tool:{n}": v for n, v in registry.versions().items()},
    }
    bundle = build_bundle(
        run_id=config.run_id,
        target_ref=f"{target.target_id}@{target.version_hash}",
        tier=profile.declared_risk_tier.value,
        regimes=sorted({r for c in controls for r in c.regimes}),
        versions=versions,
        created_at=config.as_of,
        records=records,
        decisions=decisions,
        clause_ids_by_tool=clause_ids_by_tool(controls),
        findings=findings,
        status=status,
        parent_bundle_id=parent_bundle_id,
    )
    write_bundle(bundle, config.run_dir, config.signer)
    handles.ledger.close()
    emit(config, "run_sealed", {"bundle_id": bundle.header.bundle_id, "status": status})
    return bundle


def run_audit(
    profile: SystemProfile,
    target: Target,
    catalog: Catalog,
    engine: OpaEngine,
    config: RunConfig,
    registry: ToolRegistry | None = None,
    judge: Judge | None = None,
    parent_bundle_id: str | None = None,
    extra_tools: Iterable[str] = (),
    baseline_target: Target | None = None,
) -> AuditBundle:
    """Static (B0) audit. `extra_tools` run once after evidence collection (e.g. utility tools
    for retests); with `baseline_target` they also run on it, labelled which="baseline"."""
    if registry is None:
        load_builtin_tools()
        registry = default_registry
    handles = open_run(config)
    try:
        controls = applicable_controls(catalog, profile)
        emit(config, "plan_created", {"controls": [c.id for c in controls], "planner": "static"})
        candidates: dict[str, list[EvidenceRecord]] = {}
        evidence = collect_static_evidence(
            controls, profile, target, config, handles, registry, candidates
        )
        for name in extra_tools:
            spec = registry.get(name)
            if spec is None:
                continue
            spec(tool_context(config, handles, spec.agent, target, profile))
            if baseline_target is not None:
                ctx = tool_context(config, handles, spec.agent, baseline_target, profile)
                spec(ctx, which="baseline")
        decisions = gate_controls(
            controls,
            evidence,
            profile,
            engine,
            config,
            waivers_from(handles.ledger.records()),
            judge=judge,
            candidates=candidates,
            ledger=handles.ledger,
            target_ref=f"{target.target_id}@{target.version_hash}",
        )
        return seal_run(
            profile=profile,
            target=target,
            catalog=catalog,
            engine=engine,
            config=config,
            handles=handles,
            controls=controls,
            decisions=decisions,
            registry=registry,
            parent_bundle_id=parent_bundle_id,
        )
    finally:
        handles.ledger.close()
