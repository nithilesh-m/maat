from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from maat.agents.advisor import rank_findings
from maat.catalog.c2at import render_view
from maat.catalog.metrics import (
    adequacy_score,
    clause_coverage,
    dimension_scores,
    measured_evidence_ratio,
)
from maat.evidence.bundle import read_bundle
from maat.evidence.verify import verify_run
from maat.schemas.decisions import GateOutcome

ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
)


def report_context(
    run_dir: Path, catalog, policy_version: str, regimes=("EU", "NIST", "ISO", "IN")
) -> dict:
    b = read_bundle(run_dir)
    rep = verify_run(run_dir)
    views = {}
    for reg in regimes:
        rows = render_view(b, catalog, reg, policy_version)
        if rows:
            views[reg] = {
                "rows": rows,
                "cc": clause_coverage(rows),
                "as": adequacy_score(rows),
                "mer": measured_evidence_ratio(rows, b.entries),
            }
    all_rows = [r for v in views.values() for r in v["rows"]]
    decisions = {d.clause_id: d for d in b.decisions}
    return {
        "bundle": b,
        "verify": rep,
        "views": views,
        "dimensions": dimension_scores(all_rows, catalog),
        "ranked": [
            (cid, s, decisions[cid], catalog.controls[cid]) for cid, s in rank_findings(b, catalog)
        ],
        "pending": [d for d in b.decisions if d.outcome is GateOutcome.ABSTAIN],
        "children": sorted((Path(run_dir) / "children").glob("*/bundle.dsse.json"))
        if (Path(run_dir) / "children").exists()
        else [],
    }


def render_html(ctx: dict) -> str:
    return ENV.get_template("report.html.j2").render(**ctx)


def render_pdf(html: str, out: Path) -> None:
    from weasyprint import HTML

    HTML(string=html).write_pdf(out)
