from __future__ import annotations

import numpy as np
import shap

from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool


@maat_tool(
    "shap_explain",
    "1.0.0",
    "explainability",
    requires=(Capability.PREDICT_PROBA,),
    metrics=("sensitive_in_top", "n_features"),
)
def shap_explain(ctx: ToolContext, sample_size: int = 200, top: int = 5) -> ToolResult:
    """Global SHAP importance (mean |SHAP|) of the positive-class probability; flags whether a
    sensitive attribute is among the top features."""
    t = ctx.target
    X = t.X.sample(min(sample_size, len(t.X)), random_state=0)
    explainer = shap.Explainer(
        lambda a: t.predict_proba(__import__("pandas").DataFrame(a, columns=t.feature_columns)),
        shap.maskers.Independent(X, max_samples=100),
    )
    imp = np.abs(explainer(X).values).mean(axis=0)
    ranked = sorted(zip(t.feature_columns, imp.tolist(), strict=True), key=lambda r: -r[1])
    top_names = [n for n, _ in ranked[:top]]
    sens = set(ctx.profile.sensitive_attributes)
    ref = ctx.artifacts.put_json(
        [{"feature": n, "mean_abs_shap": v} for n, v in ranked], ctx.agent, "shap.json"
    )
    return ToolResult(
        metrics={
            "sensitive_in_top": int(bool(sens & set(top_names))),
            "top_feature": top_names[0],
            "n_features": len(ranked),
        },
        samples=[{"feature": n, "mean_abs_shap": round(v, 6)} for n, v in ranked[:top]],
        artifacts=[ref],
    )
