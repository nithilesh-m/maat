from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool


@maat_tool(
    "find_proxy_features",
    "1.0.0",
    "fairness",
    requires=(Capability.PREDICT,),
    metrics=("max_proxy_auc",),
)
def find_proxy_features(ctx: ToolContext, attribute: str, top: int = 5) -> ToolResult:
    """Rank model features by how well each alone predicts the sensitive attribute (CV AUC)."""
    t = ctx.target
    s = t.data[attribute]
    scoring = "roc_auc" if s.nunique() == 2 else "roc_auc_ovr"
    rows = []
    for c in t.feature_columns:
        if c == attribute:
            continue
        x = t.data[[c]].to_numpy(float)
        auc = float(
            np.mean(cross_val_score(LogisticRegression(max_iter=500), x, s, cv=3, scoring=scoring))
        )
        rows.append({"feature": c, "auc": round(auc, 6)})
    rows.sort(key=lambda r: -r["auc"])
    return ToolResult(
        metrics={
            "max_proxy_auc": rows[0]["auc"] if rows else 0.5,
            "top_proxy": rows[0]["feature"] if rows else "",
        },
        samples=rows[:top],
    )
