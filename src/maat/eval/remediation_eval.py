from __future__ import annotations

from pathlib import Path

from maat.catalog.c2at import render_view
from maat.eval.stability import _records
from maat.evidence.bundle import read_bundle
from maat.gates.engine import policy_bundle_version

PROBE_TOOLS = {
    "probe_prompt_injection",
    "probe_jailbreak",
    "scan_pii_leakage",
    "counterfactual_swap_test",
    "output_consistency",
    "probe_ai_disclosure",
}
UTILITY = ("task_utility", "tabular_performance")


def assert_heldout(records) -> None:
    """Re-tests must use held-out probes, otherwise a mitigation could simply overfit the probes
    it was chosen on (Goodharting)."""
    bad = [
        r.id
        for r in records
        if r.tool.split("@")[0] in PROBE_TOOLS and r.params.get("split") != "heldout"
    ]
    if bad:
        raise ValueError(f"child run used non-held-out probes (Goodharting risk): {bad}")


def _metric(recs, tool: str, metric: str):
    vals = [
        r.result.get("metrics", {}).get(metric)
        for r in sorted(recs.values(), key=lambda r: r.seq)
        if r.tool.split("@")[0] == tool and r.evidence_type.value == "measured"
    ]
    return vals[-1] if vals else None


def remediation_rows(
    parent_dir: Path, child_dir: Path, catalog, regimes=("EU", "NIST")
) -> list[dict]:
    pb, cb = read_bundle(parent_dir), read_bundle(child_dir)
    precs, crecs = _records(Path(parent_dir)), _records(Path(child_dir))
    assert_heldout(crecs.values())
    pv = policy_bundle_version()
    rows = []
    for reg in regimes:
        before = {(r.control_id, r.regime_clause): r for r in render_view(pb, catalog, reg, pv)}
        for r in render_view(cb, catalog, reg, pv):
            b = before.get((r.control_id, r.regime_clause))
            pred = catalog.controls[r.control_id].predicate
            rows.append(
                {
                    "regime": reg,
                    "control_id": r.control_id,
                    "clause": r.regime_clause,
                    "before_outcome": b.outcome.value if b else None,
                    "after_outcome": r.outcome.value,
                    "before_a": b.adequacy if b else None,
                    "after_a": r.adequacy,
                    "metric": pred.metric if pred else None,
                    "metric_before": _metric(precs, pred.tool, pred.metric) if pred else None,
                    "metric_after": _metric(crecs, pred.tool, pred.metric) if pred else None,
                    "split_after": "heldout",
                }
            )
    return rows


def utility_rows(child_dir: Path) -> dict:
    recs = sorted(_records(Path(child_dir)).values(), key=lambda r: r.seq)
    u = [r for r in recs if r.tool.split("@")[0] in UTILITY]
    base = next((r for r in u if r.params.get("which") == "baseline"), None)
    after = next((r for r in reversed(u) if r.params.get("which") != "baseline"), None)
    if not base or not after:
        return {"utility_metric": None, "before": None, "after": None, "delta": None}
    key = "qa_accuracy" if "qa_accuracy" in after.result["metrics"] else "accuracy"
    b, a = base.result["metrics"][key], after.result["metrics"][key]
    return {"utility_metric": key, "before": b, "after": a, "delta": a - b}
