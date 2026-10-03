from maat.schemas.evidence import EvidenceType
from maat.tools import load_builtin_tools
from maat.tools.registry import default_registry
from tests.fakes import ctx_with
from tests.targets.test_tabular_testbed import toy


def run(tmp_path, name, target, **kw):
    load_builtin_tools()
    return default_registry.get(name)(ctx_with(tmp_path, target, agent="risk"), **kw)


def test_robustness(tmp_path):
    m = run(tmp_path, "test_robustness_tabular", toy()).result["metrics"]
    assert 0 <= m["max_accuracy_drop"] <= 1 and m["accuracy"] > 0.7


def test_drift_detected_and_gap_without_reference(tmp_path):
    t = toy()
    assert run(tmp_path / "a", "detect_drift", t).evidence_type is EvidenceType.GAP
    ref = t.data.copy()
    ref["x"] = ref["x"] + 3
    t.reference = ref
    assert run(tmp_path / "b", "detect_drift", t).result["metrics"]["drift_share"] >= 0.5
