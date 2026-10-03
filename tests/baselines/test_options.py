import json

import pytest

import maat.service as service
from maat.baselines.llm_only import run_llm_only
from maat.catalog.loader import load_catalog
from maat.config import load_config
from maat.evidence.signing import RunKey
from maat.gates.engine import OpaEngine
from maat.llm.client import LLMResponse
from maat.llm.policy import ModelPolicyError
from maat.llm.untrusted import NullScreen
from maat.runner import RunConfig
from maat.schemas.evidence import EvidenceType
from maat.service import AuditOptions
from tests.agents.test_orchestrator import Fake
from tests.fakes import (
    AS_OF,
    SEED,
    FakeChatTarget,
    fixed_clock,
    make_profile,
    robust,
    seq_ids,
    vulnerable,
)

pytestmark = pytest.mark.opa


class Says:
    def __init__(self, label):
        self.label = label

    def complete(self, messages, *, tools=None, schema=None):
        assert not tools, "B2 must not offer tools"
        return LLMResponse(
            model="m",
            cache_key="k",
            content=json.dumps(
                {
                    "label": self.label,
                    "cited_record_ids": [],
                    "cited_spans": [],
                    "confidence": 0.5,
                    "rationale": "r",
                }
            ),
        )


def _cfg(tmp_path, name="r", events=None):
    return RunConfig(
        run_id="run-o",
        run_dir=tmp_path / name,
        signer=RunKey.from_seed(SEED),
        as_of=AS_OF,
        clock=fixed_clock(),
        id_factory=seq_ids(),
        on_event=(lambda k, p: events.append((k, p))) if events is not None else None,
    )


def test_llm_only_baseline_never_probes_the_target(tmp_path):
    t = FakeChatTarget(robust)
    b = run_llm_only(make_profile(), t, load_catalog(), OpaEngine(), _cfg(tmp_path), Says("N"))
    assert t.calls == []
    assert all(e.evidence_type is EvidenceType.LLM_JUDGMENT for e in b.entries)
    assert {d.outcome.value for d in b.decisions} == {"fail"}
    assert all(d.rationale == "B2 llm-only" for d in b.decisions)


def test_options_defaults_match_the_full_system():
    o = AuditOptions()
    assert (o.planner, o.agent_layout, o.crosscheck, o.judge_mode) == (
        "agents",
        "specialists",
        True,
        "panel",
    )
    assert o.allow_same_family_judges is False and o.model_profile is None


def _agents(tmp_path, monkeypatch, options, events=None, judges=None):
    monkeypatch.setattr(service, "llm_factory", lambda role, cache, cfg: Fake())
    monkeypatch.setattr(service, "get_judges", lambda cfg, cache: judges or [])
    return service.execute_audit(
        make_profile(),
        FakeChatTarget(vulnerable),
        _cfg(tmp_path, events=events),
        load_config(),
        options,
        NullScreen(),
        auto_approve=True,
    )


def test_b1_single_layout_runs_one_agent_with_every_tool(tmp_path, monkeypatch):
    events = []
    _agents(tmp_path, monkeypatch, AuditOptions(agent_layout="single"), events)
    started = [p["agent"] for k, p in events if k == "agent_started"]
    assert started == ["single"]


def test_default_layout_runs_the_specialists(tmp_path, monkeypatch):
    events = []
    _agents(tmp_path, monkeypatch, AuditOptions(), events)
    started = [p["agent"] for k, p in events if k == "agent_started"]
    assert "risk" in started and "compliance" in started and "single" not in started


def test_a1_crosscheck_can_be_disabled(tmp_path, monkeypatch):
    built = []
    import maat.service as s

    real = s.make_crosscheck
    monkeypatch.setattr(s, "make_crosscheck", lambda *a, **k: built.append(1) or real(*a, **k))
    _agents(tmp_path, monkeypatch, AuditOptions(crosscheck=False))
    assert built == []  # the factory is never even wired


class _Judge:
    def __init__(self, name):
        self.ref = type("R", (), {"name": name})
        self.calls = 0

    def complete(self, messages, *, tools=None, schema=None):
        self.calls += 1
        rid = __import__("re").search(r'"record_id": "([^"]+)"', messages[-1]["content"])
        body = {
            "label": "S",
            "cited_record_ids": [rid.group(1)] if rid else [],
            "cited_spans": [],
            "confidence": 0.9,
            "rationale": "r",
        }
        return LLMResponse(model="j", cache_key="k", content=json.dumps(body))


@pytest.mark.parametrize("mode,expected_used", [("panel", 3), ("single", 1), ("none", 0)])
def test_a2_judge_mode_controls_how_many_judges_vote(tmp_path, monkeypatch, mode, expected_used):
    judges = [_Judge("j1"), _Judge("j2"), _Judge("j3")]
    b = _agents(tmp_path, monkeypatch, AuditOptions(judge_mode=mode), judges=judges)
    used = sum(1 for j in judges if j.calls)
    assert used == expected_used
    qual = [d for d in b.decisions if d.method == "judge_panel"]
    assert bool(qual) == (mode != "none")
    if mode == "none":
        assert any(d.method == "none" and d.outcome.value == "abstain" for d in b.decisions)


def test_a3_same_family_judges_only_with_the_explicit_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "get_judges", lambda cfg, cache: [])  # policy check only
    prof = make_profile(
        target={
            "adapter": "chat",
            "endpoint": "http://x/v1",
            "model": "m",
            "model_family": "mistral",
        }
    )
    cfg = load_config().model_copy(deep=True)
    cfg.profile = "same-family"
    cfg.llm_mode = "replay"
    with pytest.raises(ModelPolicyError, match="same family"):
        service.execute_audit(
            prof, FakeChatTarget(robust), _cfg(tmp_path, "a"), cfg,
            AuditOptions(planner="static"), NullScreen(),
        )  # fmt: skip
    service.execute_audit(
        prof, FakeChatTarget(robust), _cfg(tmp_path, "b"), cfg,
        AuditOptions(planner="static", allow_same_family_judges=True), NullScreen(),
    )  # fmt: skip


def test_a4_model_profile_selects_the_small_models(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        service,
        "llm_factory",
        lambda role, cache, cfg: seen.setdefault("p", cfg.profile) and Fake(),
    )
    monkeypatch.setattr(service, "get_judges", lambda cfg, cache: [])
    service.execute_audit(
        make_profile(), FakeChatTarget(robust), _cfg(tmp_path), load_config(),
        AuditOptions(model_profile="local-small"), NullScreen(), auto_approve=True,
    )  # fmt: skip
    assert seen["p"] == "local-small"


def test_b2_planner_dispatches_to_the_llm_only_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "llm_factory", lambda role, cache, cfg: Says("S"))
    t = FakeChatTarget(robust)
    b = service.execute_audit(
        make_profile(), t, _cfg(tmp_path), load_config(),
        AuditOptions(planner="llm_only"), NullScreen(),
    )  # fmt: skip
    assert t.calls == [] and all(e.tool == "llm_only" for e in b.entries)


def test_i6_b2_llm_failures_are_abstentions_not_detections(tmp_path):
    from maat.llm.client import LLMError

    class Broken:
        def complete(self, messages, *, tools=None, schema=None):
            raise LLMError("ollama OOM")

    b = run_llm_only(
        make_profile(),
        FakeChatTarget(robust),
        load_catalog(),
        OpaEngine(),
        _cfg(tmp_path),
        Broken(),
    )
    assert {d.outcome.value for d in b.decisions} == {"abstain"}
    assert all("unparseable" in d.rationale or "LLMError" in d.rationale for d in b.decisions)
