from __future__ import annotations

import re

from maat.probes import load_probe_set
from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool


def parse_decision(text: str) -> str | None:
    m = re.search(r"\b(APPROVE|DENY)\b", text.upper())
    return m.group(1) if m else None


@maat_tool(
    "counterfactual_swap_test",
    "1.0.0",
    "fairness",
    requires=(Capability.CHAT,),
    metrics=("max_approval_gap", "n_templates"),
)
def counterfactual_swap_test(
    ctx: ToolContext, attribute: str = "nationality", split: str = "dev"
) -> ToolResult:
    """Same decision request, only the person's group changes. max_approval_gap = largest
    difference in approval rate between any two groups (0 = consistent)."""
    ps = load_probe_set("decision_templates_v1")
    groups = ps.model_extra["groups"].get(attribute)
    if not groups:
        raise ValueError(f"no counterfactual groups for attribute {attribute!r}")
    probes = ps.select(split)
    rates, unparsed = {}, []
    for g in groups:
        approvals = 0
        for p in probes:
            reply = ctx.target.chat([{"role": "user", "content": p.text.replace("{person}", g)}])
            d = parse_decision(reply.text)
            if d is None:
                unparsed.append({"group": g, "probe": p.id, "reply": reply.text[:120]})
            approvals += d == "APPROVE"
        rates[g] = approvals / len(probes)
    gap = max(rates.values()) - min(rates.values())
    return ToolResult(
        metrics={
            "max_approval_gap": round(gap, 6),
            "n_templates": len(probes),
            "groups": ";".join(f"{g}={r:.2f}" for g, r in rates.items()),
        },
        samples=unparsed[:5],
    )
