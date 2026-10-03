import pytest
from pydantic import ValidationError

from maat.catalog.loader import CatalogError, applicable_controls, load_catalog, tier_applies
from maat.schemas.catalog import Control
from maat.schemas.findings import Finding
from tests.fakes import make_profile


def test_builtin_catalog_loads():
    cat = load_catalog()
    assert {"VG-SEC-01", "RG-TRANS-01"} <= set(cat.controls)
    assert cat.version.startswith("sha256:")
    c = cat.controls["VG-SEC-01"]
    assert c.kind == "quantitative" and c.predicate.tool == "probe_prompt_injection"
    assert c.regimes["EU"] == ["AI Act Art. 15(5)"]


def test_tier_predicates():
    assert tier_applies("R1+", 1) and tier_applies("R2+", 2) and not tier_applies("R2+", 1)
    assert tier_applies("R3", 3) and not tier_applies("R3", 2)


def test_applicability_filters_by_type_and_tier():
    cat = load_catalog()
    ids = [c.id for c in applicable_controls(cat, make_profile())]
    assert ids == sorted(ids) and "VG-SEC-01" in ids
    tab = make_profile(system_type="tabular_ml")
    assert "VG-SEC-01" not in [c.id for c in applicable_controls(cat, tab)]


def test_quantitative_needs_predicate_on_an_edge():
    with pytest.raises(ValidationError, match="predicate"):
        Control.model_validate(
            {
                "id": "VG-SEC-99",
                "title": "t",
                "dimension": "robustness_security",
                "gate": "VG",
                "kind": "quantitative",
                "agent": "risk",
                "applies_to": ["rag"],
                "tier": "R1+",
                "criticality": "high",
                "regimes": {},
                "evidence_edges": [{"tool": "a", "w": 3}],
                "predicate": {"tool": "b", "metric": "m", "op": "le", "threshold": "x"},
            }
        )


def test_qualitative_needs_rubric():
    with pytest.raises(ValidationError, match="rubric"):
        Control.model_validate(
            {
                "id": "RG-OVS-99",
                "title": "t",
                "dimension": "accountability_documentation",
                "gate": "RG",
                "kind": "qualitative",
                "agent": "compliance",
                "applies_to": ["rag"],
                "tier": "R1+",
                "criticality": "high",
                "regimes": {},
                "evidence_edges": [{"tool": "a", "w": 2}],
            }
        )


def test_bad_file_reports_filename(tmp_path):
    (tmp_path / "BAD.yaml").write_text("id: [", encoding="utf-8")
    with pytest.raises(CatalogError, match="BAD.yaml"):
        load_catalog(tmp_path)


def test_empty_dir_is_error(tmp_path):
    with pytest.raises(CatalogError, match="no controls"):
        load_catalog(tmp_path)


def test_finding_requires_evidence():
    with pytest.raises(ValidationError):
        Finding(
            id="f1",
            agent="risk",
            clause_ids=["VG-SEC-01"],
            severity="high",
            claim="x",
            evidence_ids=[],
        )
