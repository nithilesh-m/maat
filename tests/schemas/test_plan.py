from maat.catalog.loader import applicable_controls, load_catalog
from maat.schemas.plan import ERS, plan_from_controls
from tests.fakes import make_profile


def test_plan_groups_by_agent():
    plan = plan_from_controls(applicable_controls(load_catalog(), make_profile()))
    assert (
        "VG-SEC-01" in plan.assignments["risk"] and "RG-TRANS-01" in plan.assignments["compliance"]
    )


def test_ers_thresholds_are_floats():
    e = ERS(
        purpose="p",
        stakeholders=[],
        prohibited_uses=[],
        sensitive_groups=[],
        thresholds={"injection_asr_max": 0.01},
    )
    assert e.thresholds["injection_asr_max"] == 0.01
