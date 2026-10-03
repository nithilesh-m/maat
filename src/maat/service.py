"""Audit execution shared by the CLI and the HTTP API."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ulid import ULID

from maat.agents.advisor import propose_mitigations, rank_findings
from maat.agents.crosscheck import make_crosscheck
from maat.agents.orchestrator import ApprovalNeeded, OrchestratorDeps, run_agent_audit
from maat.catalog.delta import delta_summary, delta_view, utility_summary
from maat.catalog.loader import load_catalog
from maat.config import load_config
from maat.evidence.bundle import read_bundle
from maat.evidence.replay import copy_replay_inputs, load_replay
from maat.evidence.signing import RunKey
from maat.gates.engine import OpaEngine
from maat.gates.judges import make_judge
from maat.llm.cache import LLMCache
from maat.llm.client import get_client, get_judges
from maat.llm.policy import validate_model_policy
from maat.llm.untrusted import NullScreen
from maat.options import AuditOptions
from maat.profile.loader import load_profile
from maat.remediation.apply import SandboxError, apply_mitigation
from maat.remediation.catalog import MITIGATIONS
from maat.remediation.retest import retest
from maat.runner import RunConfig, RunError, run_audit
from maat.schemas.evidence import EvidenceRecord
from maat.schemas.profile import SystemProfile
from maat.schemas.remediation import MitigationPlan
from maat.targets import factory
from maat.targets.base import Target
from maat.tools import load_builtin_tools
from maat.tools.registry import default_registry
from maat.tools.services import default_services

__all__ = ["ApprovalNeeded", "AuditOptions", "build_target", "execute_audit", "replay_audit"]


def build_target(profile: SystemProfile) -> Target:  # monkeypatchable
    return factory.build_target(profile)


def make_screen(kind: str = "prompt_guard"):  # monkeypatchable
    """The untrusted-content screen. "none" disables the classifier (an operator ablation)."""
    from maat.llm.untrusted import PromptGuardScreen

    return NullScreen() if kind == "none" else PromptGuardScreen()


def llm_factory(role, cache, cfg):  # monkeypatchable
    return get_client(role, cfg, cache)


def _select_judges(judges: list, options: AuditOptions) -> list:
    return judges[:1] if options.judge_mode == "single" else judges


def lazy_judge(cfg_run, maat_cfg, screen, options: AuditOptions | None = None):
    """Panel judge for static runs; built on first use because the run dir must exist first.
    Uses llm_cache.sqlite so `maat replay` can reproduce judge verdicts from the cache."""
    options = options or AuditOptions()
    if options.judge_mode == "none":
        return None
    state = {}

    def judge(control, evidence):
        if "j" not in state:
            cache = LLMCache(cfg_run.run_dir / "llm_cache.sqlite", maat_cfg.llm_mode)
            panel = _select_judges(get_judges(maat_cfg, cache), options)
            state["j"] = make_judge(panel, OpaEngine().policy_version, screen=screen)
        return state["j"](control, evidence)

    return judge


class _LazyLLM:
    """An LLM client built on first use (the run directory must exist before its cache does)."""

    def __init__(self, role: str, cfg_run: RunConfig, maat_cfg):
        self._role, self._cfg_run, self._maat_cfg, self._client = role, cfg_run, maat_cfg, None

    def complete(self, *args, **kwargs):
        if self._client is None:
            cache = LLMCache(self._cfg_run.run_dir / "llm_cache.sqlite", self._maat_cfg.llm_mode)
            self._client = llm_factory(self._role, cache, self._maat_cfg)
        return self._client.complete(*args, **kwargs)


def execute_audit(
    prof,
    target,
    cfg_run: RunConfig,
    maat_cfg,
    options: AuditOptions,
    screen,
    resume: Callable[[dict], dict] | None = None,
    *,
    auto_approve: bool = False,
):
    if maat_cfg is not None:
        if options.model_profile:
            maat_cfg.profile = options.model_profile
        # The model policy (local_only egress, cross-family judges) applies to every planner:
        # static runs also send replies to the tool LLMs and judges named in maat.toml.
        validate_model_policy(maat_cfg, prof, options.allow_same_family_judges)
        run_dir = cfg_run.run_dir
        cfg_run.services = default_services(
            maat_cfg, lambda: LLMCache(run_dir / "tool_cache.sqlite", maat_cfg.llm_mode)
        )
    if options.planner == "static":
        return run_audit(
            prof,
            target,
            load_catalog(),
            OpaEngine(),
            cfg_run,
            judge=lazy_judge(cfg_run, maat_cfg, screen, options) if maat_cfg is not None else None,
        )
    if options.planner == "llm_only":
        from maat.baselines.llm_only import run_llm_only

        return run_llm_only(
            prof,
            target,
            load_catalog(),
            OpaEngine(),
            cfg_run,
            _LazyLLM("specialists", cfg_run, maat_cfg),
        )
    load_builtin_tools()
    deps = OrchestratorDeps(
        profile=prof,
        target=target,
        catalog=load_catalog(),
        engine=OpaEngine(),
        config=cfg_run,
        maat_config=maat_cfg,
        registry=default_registry,
        llm_factory=lambda role, cache: llm_factory(role, cache, maat_cfg),
        judges_factory=lambda cache: _select_judges(get_judges(maat_cfg, cache), options),
        screen=screen,
        auto_approve=auto_approve,
        allow_same_family=options.allow_same_family_judges,
        crosscheck_factory=(
            (lambda llm, mk: make_crosscheck(llm, default_registry, mk))
            if options.crosscheck
            else None
        ),
        options=options,
    )
    return run_agent_audit(deps, resume=resume)


def replay_audit(
    run_dir: Path, out: Path, target_builder: Callable[[SystemProfile], Target] | None = None
) -> tuple[bool, str]:
    """Re-execute a run from its ledger and LLM cache. Returns (matched, message)."""
    run_dir = Path(run_dir)
    try:
        original = read_bundle(run_dir)
        src, clock, ids, meta = load_replay(run_dir)
        prof = load_profile(run_dir / "profile.yaml")
        maat_cfg = load_config(run_dir / "maat.toml") if meta["planner"] == "agents" else None
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"cannot replay {run_dir}: {e}") from e
    if maat_cfg is not None:
        maat_cfg.llm_mode = "replay"
    new_dir = Path(out) / f"{meta['run_id']}-replay-{str(ULID())[-8:].lower()}"
    cfg_run = RunConfig(
        run_id=meta["run_id"],
        run_dir=new_dir,
        signer=RunKey.generate(),
        as_of=datetime.fromisoformat(meta["as_of"]),
        clock=clock,
        id_factory=ids,
        replay=src,
        meta={**meta, "replay_of": str(run_dir)},
    )
    target = (target_builder or build_target)(prof)

    def copy_inputs(kind, payload):  # fallback for static replays; agent runs copy earlier
        if kind == "plan_created":
            copy_replay_inputs(run_dir, new_dir)

    cfg_run.on_event = copy_inputs
    try:
        options = AuditOptions.model_validate(
            meta.get("options")
            or {
                "planner": meta["planner"],
                "allow_same_family_judges": meta.get("allow_same_family", False),
            }
        )
        b = execute_audit(prof, target, cfg_run, maat_cfg, options, NullScreen(), auto_approve=True)
    except RunError as e:  # could not even start: not evidence of divergence
        return False, f"ERROR: replay could not start: {e}"
    except Exception as e:  # noqa: BLE001 - replay reports any divergence
        return False, f"DIVERGED: {type(e).__name__}: {e}"
    if b.header.bundle_id != original.header.bundle_id:
        return False, f"DIVERGED: {b.header.bundle_id} != {original.header.bundle_id}"
    # The Merkle root covers the ledger only; decisions and findings must match too.
    for name in ("decisions", "findings", "status"):
        before = original.model_dump(mode="json")[name]
        after = b.model_dump(mode="json")[name]
        if before != after:
            return False, f"DIVERGED: {name} differ from the original run"
    return True, f"MATCH {b.header.bundle_id}"


@dataclass
class RemediationResult:
    plans: list[MitigationPlan]
    manual: list[str]
    notes: list[str] = field(default_factory=list)
    child_dir: Path | None = None
    rows: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def proposal_adapter(profile: SystemProfile) -> str:
    return "tabular" if profile.target.adapter == "tabular" else "testbed"


def top_proxy(run_dir: Path) -> str | None:
    conn = sqlite3.connect(f"file:{Path(run_dir) / 'ledger.sqlite'}?mode=ro", uri=True)
    rows = [
        EvidenceRecord.model_validate_json(b)
        for (b,) in conn.execute("SELECT body FROM evidence ORDER BY seq")
    ]
    conn.close()
    found = [
        r.result["metrics"].get("top_proxy")
        for r in rows
        if r.tool.startswith("find_proxy_features") and "metrics" in r.result
    ]
    return found[-1] if found else None


def propose(run_dir: Path, prof: SystemProfile) -> tuple[list[MitigationPlan], list[str]]:
    """Ranked mitigation plans plus failed controls that need manual follow-up."""
    parent, catalog = read_bundle(run_dir), load_catalog()
    plans = propose_mitigations(parent, catalog, proposal_adapter(prof))
    covered = {p.control_id for p in plans}
    manual = [cid for cid, _ in rank_findings(parent, catalog) if cid not in covered]
    return plans, manual


def remediate_run(
    run_dir: Path,
    prof: SystemProfile,
    *,
    apply: bool,
    signer: RunKey | None = None,
    config: Path | None = None,
    regime: str = "EU",
    target_builder: Callable[[SystemProfile], Target] | None = None,
    mitigation_ids: list[str] | None = None,
    allow_same_family_judges: bool = False,
) -> RemediationResult:
    """Propose mitigations; with apply=True mitigate a sandboxed snapshot, re-test it as a child
    run on held-out probes, and return the delta. Raises SandboxError / ValueError."""
    run_dir = Path(run_dir)
    plans, manual = propose(run_dir, prof)
    if mitigation_ids is not None:
        plans = [p for p in plans if p.mitigation_id in set(mitigation_ids)]
    result = RemediationResult(plans=plans, manual=manual)
    if not apply or not plans:
        return result
    if not prof.sandbox_allowed:
        raise SandboxError(
            "--apply needs profile.sandbox_allowed: true (mitigations touch a sandboxed snapshot)"
        )
    parent, catalog = read_bundle(run_dir), load_catalog()
    original = (target_builder or build_target)(prof)
    mitigated, applied, applied_plans = original, set(), []
    for p in plans:
        if p.mitigation_id in applied:
            applied_plans.append(p)
            continue
        spec = next(m for m in MITIGATIONS if m.id == p.mitigation_id)
        if spec.params.get("method") == "drop_feature":
            feat = top_proxy(run_dir)
            if feat is None:
                result.notes.append(
                    f"skipping {spec.id}: no find_proxy_features evidence in the parent run"
                )
                continue
            spec = spec.model_copy(update={"params": {**spec.params, "feature": feat}})
        mitigated = apply_mitigation(mitigated, prof, spec)
        applied.add(p.mitigation_id)
        applied_plans.append(p)
    out_dir = run_dir / "children"
    out_dir.mkdir(exist_ok=True)
    maat_cfg = load_config(config) if config is not None and Path(config).exists() else None
    if maat_cfg is not None:
        validate_model_policy(maat_cfg, prof, allow_same_family_judges)
    services = (
        default_services(
            maat_cfg, lambda: LLMCache(out_dir / "tool_cache.sqlite", maat_cfg.llm_mode)
        )
        if maat_cfg is not None
        else None
    )
    engine = OpaEngine()
    _, child, child_dir = retest(
        run_dir, mitigated, prof, applied_plans, catalog, engine,
        signer or RunKey.generate(), out_dir, proposal_adapter(prof),
        baseline_target=original, services=services,
    )  # fmt: skip
    result.child_dir = child_dir
    result.rows = delta_view(parent, child, catalog, regime, engine.policy_version)
    result.summary = {**delta_summary(result.rows), **utility_summary(child_dir)}
    return result
