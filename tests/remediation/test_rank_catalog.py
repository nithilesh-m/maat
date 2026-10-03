from maat.agents.advisor import propose_mitigations, rank_findings, severity_score
from maat.catalog.loader import load_catalog
from maat.remediation.catalog import mitigations_for
from maat.schemas.decisions import GateOutcome
from tests.catalog.test_c2at import E_INJ, bundle, dec

CAT = load_catalog()


def test_scores_and_ranking():
    c = CAT.controls["VG-SEC-01"]
    assert severity_score(c, dec("VG-SEC-01", GateOutcome.BLOCK), "high") == 27
    b = bundle([dec("VG-SEC-01", GateOutcome.BLOCK), dec("RG-TRANS-01", GateOutcome.PASS)], [E_INJ])
    assert [cid for cid, _ in rank_findings(b, CAT)] == ["VG-SEC-01"]


def test_proposals():
    b = bundle([dec("VG-SEC-01", GateOutcome.BLOCK)], [E_INJ])
    plans = propose_mitigations(b, CAT, "testbed")
    assert plans[0].mitigation_id == "M-HARDEN"
    assert mitigations_for("VG-SEC-01", "tabular") == []
