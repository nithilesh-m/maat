from __future__ import annotations

from sklearn.metrics import roc_auc_score

from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool
from maat.tools.risk.hallucination import load_qa


@maat_tool(
    "task_utility", "1.0.0", "risk", requires=(Capability.CHAT,), metrics=("qa_accuracy", "n")
)
def task_utility(ctx: ToolContext, which: str = "current") -> ToolResult:
    """Task utility: share of QA answers containing the reference answer's key tokens.
    `which` only labels the record (current or baseline); it does not change the measurement."""
    rows = []
    for it in load_qa(ctx):
        ans = ctx.target.chat([{"role": "user", "content": it["q"]}]).text.lower()
        keys = [w for w in str(it["a"]).lower().split() if len(w) > 2] or [str(it["a"]).lower()]
        rows.append(all(k in ans for k in keys))
    return ToolResult(metrics={"qa_accuracy": round(sum(rows) / len(rows), 6), "n": len(rows)})


@maat_tool(
    "tabular_performance",
    "1.0.0",
    "risk",
    requires=(Capability.PREDICT,),
    metrics=("accuracy", "auroc"),
)
def tabular_performance(ctx: ToolContext, which: str = "current") -> ToolResult:
    """Accuracy and (if probabilities are available) AUROC on the audited dataset.
    `which` only labels the record (current or baseline)."""
    t = ctx.target
    acc = float((t.predict(t.X) == t.y).mean())
    auc = (
        float(roc_auc_score(t.y, t.predict_proba(t.X)))
        if Capability.PREDICT_PROBA in t.capabilities()
        else -1.0
    )
    return ToolResult(metrics={"accuracy": round(acc, 6), "auroc": round(auc, 6)})
