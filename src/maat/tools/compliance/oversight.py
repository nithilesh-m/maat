from __future__ import annotations

import re
from pathlib import Path

from maat.tools.compliance.documents import parse_documents
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool

PATTERNS = {
    "oversight_evidence": r"human (oversight|review)|human-in-the-loop|override",
    "escalation_evidence": r"escalat|hand ?off|transfer to (a )?human|stop button",
}


@maat_tool(
    "check_logging_and_oversight",
    "1.0.0",
    "compliance",
    metrics=("logging_evidence", "oversight_evidence", "escalation_evidence"),
)
def check_logging_and_oversight(ctx: ToolContext) -> ToolResult:
    """Presence of interaction logs (Art. 12) and of human-oversight / escalation descriptions
    (Art. 14) with cited spans. Adequacy is judged qualitatively by the judge panel."""
    logs = ctx.profile.artifacts.logs
    log_ok = int(bool(logs) and Path(logs).exists() and Path(logs).stat().st_size > 0)
    sections = parse_documents(ctx.profile.artifacts.docs)
    metrics, samples = {"logging_evidence": log_ok}, []
    for key, rx in PATTERNS.items():
        hits = [s for s in sections if re.search(rx, f"{s.heading}\n{s.text}", re.I)]
        metrics[key] = int(bool(hits))
        samples += [
            {"kind": key, "doc": h.doc, "heading": h.heading, "text": h.text[:300]}
            for h in hits[:2]
        ]
    return ToolResult(metrics=metrics, samples=samples)
