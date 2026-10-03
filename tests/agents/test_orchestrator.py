import json

import pytest

from maat.agents.orchestrator import ApprovalNeeded, OrchestratorDeps, run_agent_audit
from maat.catalog.loader import load_catalog
from maat.config import load_config
from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from maat.gates.engine import OpaEngine
from maat.llm.client import LLMResponse, ToolCall
from maat.llm.untrusted import NullScreen
from maat.runner import RunConfig
from maat.schemas.decisions import GateOutcome
from maat.tools import load_builtin_tools
from maat.tools.registry import default_registry
from tests.fakes import AS_OF, SEED, FakeChatTarget, fixed_clock, make_profile, seq_ids, vulnerable

pytestmark = pytest.mark.opa


class Fake:
    """Classifier → declared tier; agent → calls injection probe once; findings → one finding."""

    def __init__(self):
        self.n = 0

    def complete(self, messages, *, tools=None, schema=None):
        if schema and "suggested_tier" in json.dumps(schema):
            return LLMResponse(
                model="f",
                cache_key="k",
                content=json.dumps(
                    {"system_type": "rag", "suggested_tier": "high", "rationale": "r"}
                ),
            )
        if schema:
            return LLMResponse(model="f", cache_key="k", content='{"findings": []}')
        self.n += 1
        if tools and self.n == 1:
            return LLMResponse(
                model="f",
                cache_key="k",
                tool_calls=[ToolCall(name="probe_prompt_injection", arguments={})],
            )
        return LLMResponse(model="f", cache_key="k")


def deps(tmp_path, auto):
    load_builtin_tools()
    fake = Fake()
    cfg = RunConfig(
        run_id="run-o",
        run_dir=tmp_path / "r",
        signer=RunKey.from_seed(SEED),
        as_of=AS_OF,
        clock=fixed_clock(),
        id_factory=seq_ids(),
    )
    return OrchestratorDeps(
        profile=make_profile(),
        target=FakeChatTarget(vulnerable),
        catalog=load_catalog(),
        engine=OpaEngine(),
        config=cfg,
        maat_config=load_config(),
        registry=default_registry,
        llm_factory=lambda role, cache: fake,
        judges_factory=lambda cache: [],
        screen=NullScreen(),
        auto_approve=auto,
    )


def test_agent_audit_end_to_end_auto_approve(tmp_path):
    b = run_agent_audit(deps(tmp_path, auto=True))
    d = {x.clause_id: x for x in b.decisions}
    assert d["VG-SEC-01"].outcome is GateOutcome.BLOCK
    assert b.header.tier.value == "high"  # suggested tier accepted by auto-approve
    assert any(e.tool == "approval" for e in b.entries) and verify_run(tmp_path / "r").ok


def test_interrupt_requires_answer(tmp_path):
    with pytest.raises(ApprovalNeeded):
        run_agent_audit(deps(tmp_path, auto=False))


def test_human_rejects_tier_change(tmp_path):
    b = run_agent_audit(
        deps(tmp_path, auto=False), resume=lambda p: {"approve_tier": False, "ers": None}
    )
    assert b.header.tier.value == "limited"


def test_crosscheck_factory_is_built_with_llm_and_ctx_maker(tmp_path):
    built = {}

    def factory(llm, make_ctx):
        built["ctx_agent"] = make_ctx("compliance").agent
        built["llm"] = llm

        def crosscheck(findings, records):
            built["called"] = True
            return findings

        return crosscheck

    d = deps(tmp_path, auto=True)
    d.crosscheck_factory = factory
    run_agent_audit(d)
    assert built["ctx_agent"] == "compliance" and built["called"] and built["llm"] is not None
