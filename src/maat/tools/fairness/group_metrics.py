from __future__ import annotations

from fairlearn.metrics import (
    MetricFrame,
    demographic_parity_difference,
    equalized_odds_difference,
    false_positive_rate,
    selection_rate,
    true_positive_rate,
)

from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool


@maat_tool(
    "tabular_group_metrics",
    "1.0.0",
    "fairness",
    requires=(Capability.PREDICT,),
    metrics=("dp_diff", "eo_diff", "min_group_selection", "max_group_selection", "n_groups"),
)
def tabular_group_metrics(ctx: ToolContext, attribute: str) -> ToolResult:
    """Group fairness for one sensitive attribute: demographic parity difference, equalized odds
    difference, and per-group selection/true-positive/false-positive rates."""
    t = ctx.target
    if attribute not in t.data.columns:
        raise ValueError(f"attribute {attribute!r} not in dataset columns")
    y, yp, s = t.y, t.predict(t.X), t.data[attribute]
    mf = MetricFrame(
        metrics={
            "selection": selection_rate,
            "tpr": true_positive_rate,
            "fpr": false_positive_rate,
        },
        y_true=y,
        y_pred=yp,
        sensitive_features=s,
    )
    by = mf.by_group.reset_index()
    ref = ctx.artifacts.put_json(
        by.to_dict(orient="records"), ctx.agent, f"groups_{attribute}.json"
    )
    return ToolResult(
        metrics={
            "dp_diff": round(float(demographic_parity_difference(y, yp, sensitive_features=s)), 6),
            "eo_diff": round(float(equalized_odds_difference(y, yp, sensitive_features=s)), 6),
            "min_group_selection": round(float(mf.by_group["selection"].min()), 6),
            "max_group_selection": round(float(mf.by_group["selection"].max()), 6),
            "n_groups": int(s.nunique()),
        },
        samples=by.head(10).to_dict(orient="records"),
        artifacts=[ref],
    )
