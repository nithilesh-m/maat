from __future__ import annotations

from functools import lru_cache

from rank_bm25 import BM25Okapi

from maat.catalog.loader import load_catalog
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import maat_tool


@lru_cache(maxsize=1)
def _index():
    cat = load_catalog()
    docs = [
        (c.id, f"{c.title} {c.rubric or ''} " + " ".join(x for v in c.regimes.values() for x in v))
        for c in cat.controls.values()
    ]
    return docs, BM25Okapi([t.lower().split() for _, t in docs])


def search_clause_catalog(query: str, k: int = 5) -> list[dict]:
    docs, bm = _index()
    scores = bm.get_scores(query.lower().split())
    ranked = sorted(zip(docs, scores, strict=True), key=lambda r: -r[1])[:k]
    return [{"control_id": d[0], "score": round(float(s), 4)} for d, s in ranked]


@maat_tool("search_clause_catalog", "1.0.0", "compliance", metrics=("hits",))
def search_clause_catalog_tool(ctx: ToolContext, query: str) -> ToolResult:
    """Find catalog controls relevant to a finding or topic (BM25)."""
    hits = search_clause_catalog(query)
    return ToolResult(metrics={"hits": len(hits)}, samples=hits)
