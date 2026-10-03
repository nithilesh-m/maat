from __future__ import annotations

import sqlite3
from pathlib import Path

from maat.catalog.c2at import render_view
from maat.schemas.evidence import EvidenceRecord

UTILITY_TOOLS = ("task_utility", "tabular_performance")


def delta_view(parent, child, catalog, regime, policy_version) -> list[dict]:
    before = {
        (r.control_id, r.regime_clause): r
        for r in render_view(parent, catalog, regime, policy_version)
    }
    after = {
        (r.control_id, r.regime_clause): r
        for r in render_view(child, catalog, regime, policy_version)
    }
    rows = []
    for key, a in sorted(after.items()):
        b = before.get(key)
        rows.append(
            {
                "control_id": key[0],
                "regime_clause": key[1],
                "before_outcome": b.outcome.value if b else None,
                "after_outcome": a.outcome.value,
                "before_a": b.adequacy if b else None,
                "after_a": a.adequacy,
            }
        )
    return rows


def delta_summary(rows: list[dict]) -> dict:
    n = len(rows) or 1
    b = sum(r["before_a"] or 0 for r in rows) / (3 * n)
    a = sum(r["after_a"] for r in rows) / (3 * n)
    return {"AS_before": round(b, 4), "AS_after": round(a, 4), "delta_AS": round(a - b, 4)}


def utility_summary(child_run_dir: Path) -> dict:
    """Utility metrics before (baseline) and after (mitigated target) from the child ledger."""
    conn = sqlite3.connect(f"file:{Path(child_run_dir) / 'ledger.sqlite'}?mode=ro", uri=True)
    records = [
        EvidenceRecord.model_validate_json(b)
        for (b,) in conn.execute("SELECT body FROM evidence ORDER BY seq")
    ]
    conn.close()
    out: dict = {"utility_before": None, "utility_after": None}
    for r in records:
        if r.tool.split("@")[0] not in UTILITY_TOOLS or "metrics" not in r.result:
            continue
        key = "utility_before" if r.params.get("which") == "baseline" else "utility_after"
        out[key] = r.result["metrics"]
    return out
