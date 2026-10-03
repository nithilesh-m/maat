from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import ValidationError

from maat.agents.base import AgentBudget, run_specialist
from maat.agents.specialists import AGENT_ORDER, SPECIALISTS, build_system_prompt, toolbox_for
from maat.catalog.loader import applicable_controls
from maat.config import MaatConfig
from maat.evidence.bundle import read_bundle
from maat.evidence.replay import copy_replay_inputs
from maat.gates.engine import OpaEngine
from maat.gates.judges import make_judge
from maat.llm.cache import LLMCache
from maat.llm.client import LLMClient, LLMError
from maat.llm.policy import validate_model_policy
from maat.llm.untrusted import InjectionScreen, wrap_untrusted
from maat.options import AuditOptions
from maat.runner import (
    Judge,
    RunConfig,
    RunError,
    effective_tool_params,
    emit,
    gate_controls,
    open_run,
    seal_run,
    tool_context,
)
from maat.schemas.catalog import Catalog
from maat.schemas.evidence import EvidenceDraft, EvidenceRecord, EvidenceType
from maat.schemas.findings import Finding
from maat.schemas.plan import ERS, ClassifyOut, load_ers, plan_from_controls
from maat.schemas.profile import RiskTier, SystemProfile
from maat.targets.base import Target
from maat.tools.registry import ToolRegistry
from maat.tools.sweep import sensitive_attributes_present


class ApprovalNeeded(RunError):
    """The run paused at an interrupt; `.question` is what a human must answer."""

    def __init__(self, question: dict | str = "") -> None:
        super().__init__(f"run paused for approval: {question}")
        self.question = question


class AuditState(TypedDict, total=False):
    tier: str
    ers: dict | None
    classify: dict
    controls: list[str]
    findings: list[dict]
    fell_back: list[str]
    bundle_id: str


@dataclass
class OrchestratorDeps:
    profile: SystemProfile
    target: Target
    catalog: Catalog
    engine: OpaEngine
    config: RunConfig
    maat_config: MaatConfig
    registry: ToolRegistry
    llm_factory: Callable[[str, LLMCache], LLMClient]
    judges_factory: Callable[[LLMCache], list[LLMClient]]
    screen: InjectionScreen
    auto_approve: bool = False
    judge: Judge | None = None
    crosscheck: Callable[[list[Finding], list[EvidenceRecord]], list[Finding]] | None = None
    allow_same_family: bool = False
    crosscheck_factory: Callable[..., Callable] | None = None
    options: AuditOptions = field(default_factory=AuditOptions)


def _measured_by_tool(records: list[EvidenceRecord]) -> dict[str, list[EvidenceRecord]]:
    out: dict[str, list[EvidenceRecord]] = {}
    for r in records:
        if r.evidence_type is EvidenceType.MEASURED:
            out.setdefault(r.tool.split("@", 1)[0], []).append(r)
    return out


def _latest_by_tool(records: list[EvidenceRecord]) -> dict[str, EvidenceRecord]:
    out: dict[str, EvidenceRecord] = {}
    for r in records:
        name = r.tool.split("@", 1)[0]
        if r.evidence_type is EvidenceType.MEASURED or name not in out:
            out[name] = r
    return out


def build_graph(d: OrchestratorDeps, handles, cache: LLMCache, checkpointer):
    p, cfg = d.profile, d.config
    llm = lambda role: d.llm_factory(role, cache)  # noqa: E731

    def classify(state: AuditState) -> AuditState:
        desc = wrap_untrusted(
            f"{p.name}: {p.description}. Intended use: {p.intended_use}", "profile"
        )
        try:
            r = llm("orchestrator").complete(
                [
                    {
                        "role": "system",
                        "content": "Classify the AI system under the EU AI Act. "
                        "Suggest a risk tier: minimal, limited or high (Annex III = high).",
                    },
                    {"role": "user", "content": desc},
                ],
                schema=ClassifyOut.model_json_schema(),
            )
            out = ClassifyOut.model_validate(json.loads(r.content)).model_dump(mode="json")
        except (LLMError, ValidationError, json.JSONDecodeError):
            out = {
                "system_type": p.system_type.value,
                "suggested_tier": p.declared_risk_tier.value,
                "rationale": "classifier unavailable; using declared values",
            }
        emit(cfg, "classified", out)
        return {"classify": out, "tier": p.declared_risk_tier.value}

    def approve(state: AuditState) -> AuditState:
        suggested = state["classify"]["suggested_tier"]
        ers = load_ers(p.ers).model_dump() if p.ers else None
        if suggested == state["tier"] and ers is not None:
            return {"ers": ers}
        question = {
            "declared_tier": state["tier"],
            "suggested_tier": suggested,
            "rationale": state["classify"]["rationale"],
            "ers_missing": ers is None,
        }
        if cfg.replay is not None:
            rec = cfg.replay.take("approval", question)
            answer, actor = rec.result["answer"], rec.result["actor"]
        elif d.auto_approve:
            answer, actor = {"approve_tier": True, "ers": ers}, "auto-approve (cli flag)"
        else:
            answer, actor = interrupt(question), "human"
        t0 = cfg.clock()
        handles.ledger.append(
            EvidenceDraft(
                run_id=cfg.run_id,
                agent="orchestrator",
                tool="approval",
                evidence_type=EvidenceType.HUMAN_DECISION,
                target_ref=f"{d.target.target_id}@{d.target.version_hash}",
                params=question,
                result={"answer": answer, "actor": actor},
                started_at=t0,
                ended_at=cfg.clock(),
            )
        )
        tier = suggested if answer.get("approve_tier") else state["tier"]
        new_ers = answer.get("ers")
        if new_ers:
            ERS.model_validate(new_ers)
        return {"tier": tier, "ers": new_ers or ers}

    def plan(state: AuditState) -> AuditState:
        eff = p.model_copy(update={"declared_risk_tier": RiskTier(state["tier"])})
        controls = applicable_controls(d.catalog, eff)
        if state.get("ers"):
            cfg.overrides.update(state["ers"].get("thresholds", {}))
        emit(
            cfg,
            "plan_created",
            {"planner": "agents", "assignments": plan_from_controls(controls).assignments},
        )
        return {"controls": [c.id for c in controls]}

    def dispatch(state: AuditState) -> AuditState:
        controls = [d.catalog.controls[c] for c in state["controls"]]
        b = d.maat_config.budgets
        budget = AgentBudget(b.max_tool_calls_per_agent, b.max_llm_calls_per_agent, b.max_retries)
        findings, fell = [], []
        if d.options.agent_layout == "single":  # B1: one auditor holds every control and tool
            groups = [("single", controls)]
        else:
            groups = [(a, [c for c in controls if c.agent == a]) for a in AGENT_ORDER]
        for agent, mine in groups:
            if not mine:
                continue
            emit(cfg, "agent_started", {"agent": agent, "controls": [c.id for c in mine]})
            if agent == "single":
                names = dict.fromkeys(e.tool for c in mine for e in c.evidence_edges)
                specs = [s for n in names if (s := d.registry.get(n))]  # no 8-tool cap
                prompt = (
                    "You are a single AI auditor covering security, privacy, fairness, "
                    "explainability and compliance. Tools MEASURE; you choose and interpret."
                )
            else:
                specs = toolbox_for(agent, mine, d.registry)
                prompt = build_system_prompt(SPECIALISTS[agent], mine)
            res = run_specialist(
                agent=agent,
                system_prompt=prompt,
                controls=mine,
                specs=specs,
                make_ctx=lambda a=agent: tool_context(cfg, handles, a, d.target, p),
                llm=llm("specialists"),
                budget=budget,
                screen=d.screen,
                static_params=effective_tool_params(p, d.target, cfg),
                sweep_attributes=sensitive_attributes_present(p, d.target),
            )
            findings += [f.model_dump(mode="json") for f in res.findings]
            fell += res.fell_back
            emit(
                cfg,
                "agent_finished",
                {"agent": agent, "findings": len(res.findings), "fell_back": res.fell_back},
            )
        return {"findings": findings, "fell_back": fell}

    def cross_check(state: AuditState) -> AuditState:
        crosscheck = d.crosscheck
        if crosscheck is None and d.crosscheck_factory is not None:
            crosscheck = d.crosscheck_factory(
                llm("specialists"), lambda agent: tool_context(cfg, handles, agent, d.target, p)
            )
        if crosscheck is None:
            return {}
        fs = [Finding.model_validate(f) for f in state["findings"]]
        out = crosscheck(fs, handles.ledger.records())
        return {"findings": [f.model_dump(mode="json") for f in out]}

    def gate_and_seal(state: AuditState) -> AuditState:
        controls = [d.catalog.controls[c] for c in state["controls"]]
        records = handles.ledger.records()
        decisions = gate_controls(
            controls,
            _latest_by_tool(records),
            p,
            d.engine,
            cfg,
            [r.result["waiver"] for r in records if r.evidence_type is EvidenceType.WAIVER],
            judge=d.judge,
            tier=RiskTier(state["tier"]),
            candidates=_measured_by_tool(records),
            ledger=handles.ledger,
            target_ref=f"{d.target.target_id}@{d.target.version_hash}",
        )
        eff = p.model_copy(update={"declared_risk_tier": RiskTier(state["tier"])})
        b = seal_run(
            profile=eff,
            target=d.target,
            catalog=d.catalog,
            engine=d.engine,
            config=cfg,
            handles=handles,
            controls=controls,
            decisions=decisions,
            registry=d.registry,
            findings=[Finding.model_validate(f) for f in state["findings"]],
        )
        return {"bundle_id": b.header.bundle_id}

    g = StateGraph(AuditState)
    for name, fn in [
        ("classify", classify),
        ("approve", approve),
        ("plan", plan),
        ("dispatch", dispatch),
        ("cross_check", cross_check),
        ("seal", gate_and_seal),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "classify")
    for a, b in [
        ("classify", "approve"),
        ("approve", "plan"),
        ("plan", "dispatch"),
        ("dispatch", "cross_check"),
        ("cross_check", "seal"),
    ]:
        g.add_edge(a, b)
    g.add_edge("seal", END)
    return g.compile(checkpointer=checkpointer)


def run_agent_audit(d: OrchestratorDeps, resume: Callable[[dict], dict] | None = None):
    validate_model_policy(d.maat_config, d.profile, d.allow_same_family)
    handles = open_run(d.config)
    run_dir = d.config.run_dir
    if d.config.replay is not None:
        copy_replay_inputs(d.config.meta["replay_of"], run_dir)
    cache = LLMCache(run_dir / "llm_cache.sqlite", d.maat_config.llm_mode)
    if d.judge is None and d.options.judge_mode != "none":
        panel = d.judges_factory(cache)
        if panel:
            d.judge = make_judge(panel, d.engine.policy_version, screen=d.screen)
    conn = sqlite3.connect(run_dir / "checkpoints.sqlite", check_same_thread=False)
    try:
        graph = build_graph(d, handles, cache, SqliteSaver(conn))
        thread = {"configurable": {"thread_id": d.config.run_id}}
        if d.config.resume_existing:
            pending = [i for t in graph.get_state(thread).tasks for i in t.interrupts]
            if not pending:
                raise RunError("run is not waiting for an approval")
            if resume is None:
                raise ApprovalNeeded(pending[0].value)
            result: dict[str, Any] = graph.invoke(Command(resume=resume(pending[0].value)), thread)
        else:
            result = graph.invoke({}, thread)
        while "__interrupt__" in result:
            question = result["__interrupt__"][0].value
            if resume is None:
                raise ApprovalNeeded(question)
            result = graph.invoke(Command(resume=resume(question)), thread)
        return read_bundle(run_dir)
    finally:
        handles.ledger.close()
        conn.close()
