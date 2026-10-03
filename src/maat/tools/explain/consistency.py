from __future__ import annotations

from maat.probes import load_probe_set
from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool
from maat.tools.services import cosine


@maat_tool(
    "output_consistency",
    "1.0.0",
    "explainability",
    requires=(Capability.CHAT,),
    metrics=("consistency_rate", "n"),
)
def output_consistency(ctx: ToolContext, split: str = "dev", threshold: float = 0.85) -> ToolResult:
    """Paraphrased questions should get semantically equivalent answers (embedding cosine)."""
    rows = []
    for p in load_probe_set("paraphrase_v1").select(split):
        a = ctx.target.chat([{"role": "user", "content": p.text}]).text
        b = ctx.target.chat([{"role": "user", "content": p.model_extra["alt"]}]).text
        ea, eb = ctx.services.embed([a, b])
        s = cosine(ea, eb)
        rows.append({"probe_id": p.id, "similarity": round(s, 4), "consistent": s >= threshold})
    n = len(rows)
    return ToolResult(
        metrics={"consistency_rate": round(sum(r["consistent"] for r in rows) / n, 6), "n": n},
        samples=rows[:5],
    )
