from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool

ANNEX_IV = {
    "intended_purpose": r"intended (purpose|use)",
    "system_description": r"system (description|overview)|architecture",
    "training_data": r"training data|data sources|dataset",
    "data_governance": r"data governance|provenance|lineage",
    "performance_metrics": r"accuracy|performance metric|evaluation",
    "limitations": r"limitation|known issue",
    "risk_management": r"risk (management|assessment)",
    "human_oversight": r"human oversight|human-in-the-loop",
    "logging": r"logging|record[- ]keeping|audit log",
    "post_market": r"post[- ]market|monitoring plan",
}
MODEL_CARD = {
    "model_details": r"model details|model (name|version)",
    "intended_use": r"intended (use|purpose)",
    "factors": r"factors|subgroup|demographic",
    "metrics": r"metric|accuracy",
    "evaluation_data": r"evaluation data|test set",
    "training_data": r"training data",
    "ethical_considerations": r"ethical|bias|fairness",
    "caveats": r"caveat|limitation|recommendation",
}
SCHEMAS = {"annex_iv": ANNEX_IV, "model_card": MODEL_CARD}


@dataclass(frozen=True)
class DocSection:
    doc: str
    heading: str
    text: str


def parse_documents(paths: list[str | Path]) -> list[DocSection]:
    out: list[DocSection] = []
    for p in map(Path, paths):
        if p.suffix.lower() == ".pdf":
            from pypdf import PdfReader

            text = "\n".join(pg.extract_text() or "" for pg in PdfReader(p).pages)
            out.append(DocSection(p.name, "", text))
            continue
        heading, buf = "", []
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("#"):
                if buf or heading:
                    out.append(DocSection(p.name, heading, "\n".join(buf)))
                heading, buf = line.lstrip("#").strip(), []
            else:
                buf.append(line)
        out.append(DocSection(p.name, heading, "\n".join(buf)))
    return out


@maat_tool(
    "check_doc_completeness", "1.0.0", "compliance", metrics=("completeness", "present", "required")
)
def check_doc_completeness(ctx: ToolContext, schema: str = "annex_iv") -> ToolResult:
    """Deterministic field checklist (EU AI Act Annex IV or model card) over supplied documents."""
    fields = SCHEMAS[schema]
    sections = parse_documents(ctx.profile.artifacts.docs)
    found = []
    for name, rx in fields.items():
        hit = next((s for s in sections if re.search(rx, f"{s.heading}\n{s.text}", re.I)), None)
        found.append(
            {
                "field": name,
                "present": hit is not None,
                "span": (f"{hit.doc}: {hit.heading}" if hit else None),
            }
        )
    k = sum(f["present"] for f in found)
    return ToolResult(
        metrics={"completeness": round(k / len(fields), 6), "present": k, "required": len(fields)},
        samples=found,
    )
