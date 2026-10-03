from __future__ import annotations

from maat.probes import load_probe_set
from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool
from maat.tools.services import require_services


def load_behaviors(split: str) -> list[str]:
    from datasets import load_dataset

    goals = [
        r["Goal"]
        for r in load_dataset("JailbreakBench/JBB-Behaviors", "behaviors", split="harmful")
    ]
    return goals[:70] if split == "dev" else goals[70:]


@maat_tool(
    "probe_jailbreak",
    "1.0.0",
    "risk",
    requires=(Capability.CHAT,),
    metrics=("asr", "n", "unsafe"),
    timeout=3600,
)
def probe_jailbreak(ctx: ToolContext, split: str = "dev", limit: int = 20) -> ToolResult:
    """Jailbreak templates x JailbreakBench behaviours; a local guard model judges replies.
    asr = share of attempts producing unsafe content."""
    require_services(ctx)
    templates = load_probe_set("jailbreak_templates_v1").probes
    outcomes = []
    for goal in load_behaviors(split)[:limit]:
        for t in templates:
            prompt = t.text.replace("{goal}", goal)
            reply = ctx.target.chat([{"role": "user", "content": prompt}])
            outcomes.append(
                {
                    "template": t.id,
                    "unsafe": ctx.services.guard(prompt, reply.text),
                    "goal": goal,
                    "reply": reply.text[:500],
                }
            )
    k = sum(o["unsafe"] for o in outcomes)
    ref = ctx.artifacts.put_json(
        {"outcomes": outcomes}, ctx.agent, "jailbreak.json", sensitive=True
    )
    return ToolResult(
        metrics={"asr": round(k / len(outcomes), 6), "n": len(outcomes), "unsafe": k},
        samples=[{"template": o["template"], "unsafe": o["unsafe"]} for o in outcomes[:5]],
        artifacts=[ref],
    )
