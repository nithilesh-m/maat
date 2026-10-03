from datetime import UTC, datetime

import pytest

from maat.catalog.loader import load_catalog
from maat.gates.engine import GateEngineError, OpaEngine, policy_bundle_version
from maat.schemas.decisions import GateOutcome
from maat.schemas.evidence import EvidenceRecord
from maat.schemas.profile import RiskTier

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def rec(asr: float) -> EvidenceRecord:
    return EvidenceRecord(
        run_id="r",
        agent="risk",
        tool="probe_prompt_injection@1.0.0",
        evidence_type="measured",
        target_ref="t",
        result={"metrics": {"asr": asr}, "samples": []},
        started_at=NOW,
        ended_at=NOW,
        id="rec-1",
        seq=0,
        prev_hash="sha256:0",
        signer="k",
        hash="sha256:h",
        sig="s",
    )


def test_policy_version_stable_without_opa():
    assert policy_bundle_version() == policy_bundle_version()
    assert policy_bundle_version().startswith("sha256:")


@pytest.mark.opa
@pytest.mark.parametrize("asr,outcome", [(0.0, GateOutcome.PASS), (0.28, GateOutcome.BLOCK)])
def test_decide(asr, outcome):
    ctrl = load_catalog().controls["VG-SEC-01"]
    ev = {"probe_prompt_injection": rec(asr)}
    d = OpaEngine().decide(ctrl, ev, RiskTier.LIMITED, [], {}, NOW)
    assert d.outcome is outcome and d.method == "rego" and d.inputs == ["rec-1"]
    assert d.policy_version == policy_bundle_version()


@pytest.mark.opa
def test_no_evidence_blocks():
    ctrl = load_catalog().controls["VG-SEC-01"]
    d = OpaEngine().decide(ctrl, {}, RiskTier.LIMITED, [], {}, NOW)
    assert d.outcome is GateOutcome.BLOCK and d.rationale == "no measured evidence"


@pytest.mark.opa
def test_gap_records_are_not_evidence():
    ctrl = load_catalog().controls["VG-SEC-01"]
    gap = rec(0.0).model_copy(update={"evidence_type": "gap", "result": {"error": "x"}})
    d = OpaEngine().decide(ctrl, {"probe_prompt_injection": gap}, RiskTier.LIMITED, [], {}, NOW)
    assert d.outcome is GateOutcome.BLOCK


def test_missing_binary_is_clear_error():
    with pytest.raises(GateEngineError, match="opa binary not found"):
        OpaEngine(opa_bin="definitely-not-opa")
