from datetime import timedelta

import pytest

from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from maat.review.queue import Waiver, add_waiver, pending_reviews, record_human_decision
from maat.schemas.decisions import GateOutcome
from tests.fakes import AS_OF, robust, vulnerable
from tests.test_runner import audit

pytestmark = pytest.mark.opa
REVIEWER = RunKey.from_seed(b"\x05" * 32)


def test_waiver_reseals_and_verifies(tmp_path):
    b0 = audit(tmp_path / "r", vulnerable)
    w = Waiver(
        id="W-1",
        clause_id="VG-SEC-01",
        owner="Privacy Officer",
        scope="dev split",
        expiry=AS_OF + timedelta(days=14),
        compensations=["assistive mode"],
    )
    b1 = add_waiver(tmp_path / "r", w, REVIEWER, AS_OF)
    d = next(x for x in b1.decisions if x.clause_id == "VG-SEC-01")
    assert d.outcome is GateOutcome.WAIVE and d.waiver_id == "W-1"
    assert b1.header.revision == 1 and b1.header.previous_bundle_id == b0.header.bundle_id
    assert verify_run(tmp_path / "r").ok and REVIEWER.public_key_b64 in b1.header.signers


def test_human_decision_resolves_abstain(tmp_path):
    audit(tmp_path / "r", robust)
    # RG-OVS-01 is qualitative with no judge configured in this static run -> abstain
    assert any(d.clause_id == "RG-OVS-01" for d in pending_reviews(tmp_path / "r"))
    b = record_human_decision(
        tmp_path / "r", "RG-OVS-01", "N", "a.reviewer", "no oversight doc", REVIEWER, AS_OF
    )
    d = next(x for x in b.decisions if x.clause_id == "RG-OVS-01")
    assert d.outcome is GateOutcome.FAIL and d.method == "human"
    assert all(x.clause_id != "RG-OVS-01" for x in pending_reviews(tmp_path / "r"))
    assert b.status == "pending_review"  # the catalog has many other qualitative controls


def test_status_complete_once_every_abstain_is_resolved(tmp_path):
    audit(tmp_path / "r", robust)
    b = None
    for pending in pending_reviews(tmp_path / "r"):
        b = record_human_decision(
            tmp_path / "r", pending.clause_id, "S", "a.reviewer", "ok", REVIEWER, AS_OF
        )
    assert b is not None and b.status == "complete" and b.header.revision >= 1
    assert verify_run(tmp_path / "r").ok


def test_refuses_tampered_run(tmp_path):
    audit(tmp_path / "r", robust)
    (tmp_path / "r" / "bundle.dsse.json").write_text("{}")
    with pytest.raises(ValueError, match="verify"):
        record_human_decision(tmp_path / "r", "RG-OVS-01", "S", "x", "y", REVIEWER, AS_OF)
