import pytest

from maat.catalog.loader import load_catalog
from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from maat.gates.engine import OpaEngine
from maat.runner import RunConfig, RunError, run_audit
from maat.schemas.decisions import GateOutcome
from maat.schemas.evidence import EvidenceType
from maat.tools.registry import ToolRegistry
from tests.fakes import (
    AS_OF,
    SEED,
    FakeChatTarget,
    broken,
    fixed_clock,
    make_profile,
    robust,
    seq_ids,
    vulnerable,
)

pytestmark = pytest.mark.opa


def audit(run_dir, responder, events=None, registry=None):
    cfg = RunConfig(
        run_id="run-test",
        run_dir=run_dir,
        signer=RunKey.from_seed(SEED),
        as_of=AS_OF,
        clock=fixed_clock(),
        id_factory=seq_ids(),
        on_event=(lambda k, p: events.append(k)) if events is not None else None,
    )
    return run_audit(
        make_profile(),
        FakeChatTarget(responder),
        load_catalog(),
        OpaEngine(),
        cfg,
        registry=registry,
    )


def decision(b, cid):
    return next(d for d in b.decisions if d.clause_id == cid)


def test_vulnerable_bot_blocked_and_bundle_verifies(tmp_path):
    events = []
    b = audit(tmp_path / "r", vulnerable, events)
    assert decision(b, "VG-SEC-01").outcome is GateOutcome.BLOCK
    assert "asr=1" in decision(b, "VG-SEC-01").rationale
    assert verify_run(tmp_path / "r").ok
    assert events[0] == "plan_created" and events[-1] == "run_sealed"


def test_robust_bot_passes(tmp_path):
    assert decision(audit(tmp_path / "r", robust), "VG-SEC-01").outcome is GateOutcome.PASS


def test_control_without_registered_tool_is_gap(tmp_path):
    b = audit(tmp_path / "r", robust, registry=ToolRegistry())  # no tools registered at all
    d = decision(b, "RG-TRANS-01")
    assert d.outcome is GateOutcome.BLOCK and d.rationale == "no measured evidence"
    gaps = [e for e in b.entries if e.evidence_type is EvidenceType.GAP]
    assert any(e.clause_ids == ["RG-TRANS-01"] for e in gaps)


# Review Focus #3
def test_dead_target_completes_with_gap(tmp_path):
    b = audit(tmp_path / "r", broken)
    assert decision(b, "VG-SEC-01").outcome is GateOutcome.BLOCK
    assert any(
        e.tool == "probe_prompt_injection@1.0.0" and e.evidence_type is EvidenceType.GAP
        for e in b.entries
    )
    assert verify_run(tmp_path / "r").ok


# Review Focus #4
def test_existing_run_dir_refused(tmp_path):
    audit(tmp_path / "r", robust)
    before = (tmp_path / "r" / "ledger.sqlite").read_bytes()
    with pytest.raises(RunError, match="already exists"):
        audit(tmp_path / "r", robust)
    assert (tmp_path / "r" / "ledger.sqlite").read_bytes() == before


def test_same_inputs_same_bundle_id(tmp_path):
    a = audit(tmp_path / "a", vulnerable)
    b = audit(tmp_path / "b", vulnerable)
    assert a.header.bundle_id == b.header.bundle_id


def test_run_meta_written(tmp_path):
    from maat.runner import RunConfig, run_audit

    cfg = RunConfig(
        run_id="run-test",
        run_dir=tmp_path / "r",
        signer=RunKey.from_seed(SEED),
        as_of=AS_OF,
        clock=fixed_clock(),
        id_factory=seq_ids(),
        meta={"planner": "static"},
    )
    run_audit(make_profile(), FakeChatTarget(robust), load_catalog(), OpaEngine(), cfg)
    assert '"planner": "static"' in (tmp_path / "r" / "run_meta.json").read_text()


def test_static_planner_derives_attribute_param_for_fairness_tools(tmp_path):
    from tests.targets.test_tabular_testbed import toy

    prof = make_profile(
        system_type="tabular_ml",
        declared_risk_tier="high",
        sensitive_attributes=["SEX"],
        target={"adapter": "tabular", "model_family": "sklearn"},
    )
    cfg = RunConfig(
        run_id="run-t",
        run_dir=tmp_path / "r",
        signer=RunKey.from_seed(SEED),
        as_of=AS_OF,
        clock=fixed_clock(),
        id_factory=seq_ids(),
    )
    b = run_audit(prof, toy(), load_catalog(), OpaEngine(), cfg)
    assert decision(b, "VG-FAIR-01").rationale != "no measured evidence"
    assert "dp_diff=" in decision(b, "VG-FAIR-01").rationale


def test_run_audit_forwards_judge_for_qualitative_controls(tmp_path):
    from maat.schemas.decisions import GateDecision

    def judge(control, evidence):
        return GateDecision(
            clause_id=control.id,
            gate=control.gate,
            method="judge_panel",
            policy_version="p",
            outcome=GateOutcome.PASS,
            rationale="stub panel",
        )

    cfg = RunConfig(
        run_id="run-j",
        run_dir=tmp_path / "r",
        signer=RunKey.from_seed(SEED),
        as_of=AS_OF,
        clock=fixed_clock(),
        id_factory=seq_ids(),
    )
    b = run_audit(
        make_profile(), FakeChatTarget(robust), load_catalog(), OpaEngine(), cfg, judge=judge
    )
    assert decision(b, "RG-OVS-01").rationale == "stub panel"
    assert b.status == "complete"
