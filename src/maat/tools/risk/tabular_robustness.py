from __future__ import annotations

import numpy as np

from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool


@maat_tool(
    "test_robustness_tabular",
    "1.0.0",
    "risk",
    requires=(Capability.PREDICT,),
    metrics=("accuracy", "accuracy_noise", "accuracy_missing", "max_accuracy_drop"),
)
def test_robustness_tabular(
    ctx: ToolContext, noise: float = 0.1, missing: float = 0.1, seed: int = 0
) -> ToolResult:
    """Accuracy under Gaussian feature noise and random missingness (median-imputed)."""
    t, rng = ctx.target, np.random.default_rng(seed)
    X, y = t.X.copy(), t.y
    acc = lambda Xv: float((t.predict(Xv) == y).mean())  # noqa: E731
    num = [c for c in X.columns if np.issubdtype(X[c].dtype, np.number) and X[c].nunique() > 20]
    Xn = X.copy()
    for c in num:
        Xn[c] = Xn[c] + rng.normal(0, noise * X[c].std(), len(X))
    Xm = X.copy()
    for c in X.columns:
        mask = rng.random(len(X)) < missing
        Xm.loc[mask, c] = X[c].median()
    base, a_n, a_m = acc(X), acc(Xn), acc(Xm)
    return ToolResult(
        metrics={
            "accuracy": round(base, 6),
            "accuracy_noise": round(a_n, 6),
            "accuracy_missing": round(a_m, 6),
            "max_accuracy_drop": round(max(0.0, base - min(a_n, a_m)), 6),
        }
    )
