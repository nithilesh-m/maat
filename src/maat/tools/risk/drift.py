from __future__ import annotations

import numpy as np
from scipy.stats import chi2_contingency, ks_2samp

from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool


def psi(ref: np.ndarray, cur: np.ndarray, bins: int = 10) -> float:
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    r = np.histogram(ref, edges)[0] / len(ref) + 1e-6
    c = np.histogram(np.clip(cur, edges[0], edges[-1]), edges)[0] / len(cur) + 1e-6
    return float(np.sum((c - r) * np.log(c / r)))


@maat_tool(
    "detect_drift",
    "1.0.0",
    "risk",
    requires=(Capability.PREDICT,),
    metrics=("drift_share", "n_features", "max_psi"),
)
def detect_drift(ctx: ToolContext, alpha: float = 0.01) -> ToolResult:
    """Per-feature drift between the reference (training) data and the audited data:
    KS test (numeric) or chi-square (categorical); drift_share = share of drifted features."""
    t = ctx.target
    if getattr(t, "reference", None) is None:
        raise ValueError("no reference dataset (profile.tabular.reference_dataset)")
    ref, cur = t.reference[t.feature_columns], t.X
    rows = []
    for c in t.feature_columns:
        if ref[c].nunique() <= 20:
            cats = sorted(set(ref[c]) | set(cur[c]))
            table = [
                [int((ref[c] == v).sum()) for v in cats],
                [int((cur[c] == v).sum()) for v in cats],
            ]
            p = float(chi2_contingency(table)[1])
            s = 0.0
        else:
            p = float(ks_2samp(ref[c], cur[c]).pvalue)
            s = psi(ref[c].to_numpy(float), cur[c].to_numpy(float))
        rows.append({"feature": c, "p_value": round(p, 6), "psi": round(s, 6), "drift": p < alpha})
    n = len(rows)
    return ToolResult(
        metrics={
            "drift_share": round(sum(r["drift"] for r in rows) / n, 6),
            "n_features": n,
            "max_psi": max(r["psi"] for r in rows),
        },
        samples=[r for r in rows if r["drift"]][:5],
    )
