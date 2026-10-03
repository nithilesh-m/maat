import pytest

from maat.catalog.c2at import VersionMismatchError, adequacy, render_markdown, render_view
from maat.catalog.loader import load_catalog
from maat.catalog.metrics import (
    adequacy_score,
    clause_coverage,
    dimension_scores,
    measured_evidence_ratio,
)
from maat.schemas.bundle import AuditBundle, BundleEntry, BundleHeader
from maat.schemas.decisions import GateDecision, GateOutcome
from maat.schemas.findings import Finding
from tests.fakes import AS_OF

CAT = load_catalog()


def entry(rid, etype, tool, cids):
    return BundleEntry(
        record_id=rid,
        seq=int(rid[-1]),
        hash=f"sha256:{rid}aaaaaaaaaaaa",
        evidence_type=etype,
        tool=tool,
        clause_ids=cids,
    )


def dec(cid, outcome, **kw):
    return GateDecision(
        clause_id=cid, gate="VG", method="rego", policy_version="p", outcome=outcome, **kw
    )


def bundle(decisions, entries, findings=()):
    h = BundleHeader(
        bundle_id="sha256:bid",
        run_id="run-1",
        target_ref="t",
        tier="limited",
        regimes=["EU"],
        versions={"catalog": CAT.version, "policies": "p"},
        created_at=AS_OF,
        signers=["k"],
    )
    return AuditBundle(header=h, entries=entries, decisions=decisions, findings=list(findings))


E_INJ = entry("rec-0", "measured", "probe_prompt_injection@1.0.0", ["VG-SEC-01"])
E_GAP = entry("rec-1", "gap", "none", ["RG-TRANS-01"])


def test_adequacy_levels():
    c = CAT.controls["VG-SEC-01"]
    assert adequacy(c, dec("VG-SEC-01", GateOutcome.PASS), [E_INJ], []) == 3
    assert adequacy(c, dec("VG-SEC-01", GateOutcome.BLOCK), [E_INJ], []) == 0
    assert adequacy(c, dec("VG-SEC-01", GateOutcome.WAIVE), [E_INJ], []) == 1
    disputed = Finding(
        id="f",
        agent="risk",
        clause_ids=["VG-SEC-01"],
        severity="high",
        claim="c",
        evidence_ids=["rec-0"],
        status="disputed",
    )
    assert adequacy(c, dec("VG-SEC-01", GateOutcome.PASS), [E_INJ], [disputed]) == 2


def test_golden_eu_view():
    b = bundle(
        [
            dec("VG-SEC-01", GateOutcome.PASS, rationale="asr=0 le 0.05"),
            dec("RG-TRANS-01", GateOutcome.BLOCK, rationale="no measured evidence"),
        ],
        [E_INJ, E_GAP],
    )
    rows = render_view(b, CAT, "EU", "p")
    md = render_markdown(rows, regime="EU", bundle=b)
    assert md == (
        "# EU view - bundle sha256:bid\n"
        "\n"
        "| Regime clause | Control | Outcome | a_c | Evidence |\n"
        "|---|---|---|---|---|\n"
        "| AI Act Art. 15(5) | VG-SEC-01 | pass | 3 | rec-0 (sha256:rec-0aaa) |\n"
        "| AI Act Art. 50(1) | RG-TRANS-01 | block | 0 | rec-1 (sha256:rec-1aaa) |\n"
        "\n"
        "CC = 0.500\n"
        "AS = 0.500\n"
        "MER = 1.000\n"
    )
    assert render_markdown(render_view(b, CAT, "EU", "p"), regime="EU", bundle=b) == md


def test_metrics():
    b = bundle(
        [dec("VG-SEC-01", GateOutcome.PASS), dec("RG-TRANS-01", GateOutcome.BLOCK)], [E_INJ, E_GAP]
    )
    rows = render_view(b, CAT, "EU", "p")
    assert clause_coverage(rows) == 0.5 and adequacy_score(rows) == 0.5
    assert measured_evidence_ratio(rows, b.entries) == 1.0
    ds = dimension_scores(rows, CAT)
    assert ds["robustness_security"] == 1.0 and ds["transparency_explainability"] == 0.0


def test_unmapped_regime_renders_message():
    b = bundle([dec("VG-SEC-01", GateOutcome.PASS)], [E_INJ])
    rows = render_view(b, CAT, "XX", "p")
    assert rows == [] and "No controls in this bundle map to regime XX" in render_markdown(
        rows, regime="XX", bundle=b
    )
    assert clause_coverage([]) == 0.0 and adequacy_score([]) == 0.0


def test_version_mismatch_aborts():
    b = bundle([dec("VG-SEC-01", GateOutcome.PASS)], [E_INJ])
    with pytest.raises(VersionMismatchError, match="policies"):
        render_view(b, CAT, "EU", "other-policy-version")
