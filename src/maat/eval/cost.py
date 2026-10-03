from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


def _cache_usage(p: Path) -> tuple[int, int, int]:
    if not p.exists():
        return 0, 0, 0
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        rows = [json.loads(r) for (r,) in c.execute("SELECT response FROM llm_cache")]
    except sqlite3.DatabaseError:
        rows = []
    finally:
        c.close()
    return (
        sum(r.get("prompt_eval_count", 0) for r in rows),
        sum(r.get("eval_count", 0) for r in rows),
        len(rows),
    )


def cost_rows(run_dir: Path) -> dict:
    """Tokens and LLM calls from the response caches, wall-clock from the ledger. One GPU is
    assumed, so `gpu_hours_est` is wall-clock hours (an estimate, documented as such)."""
    run_dir = Path(run_dir)
    pt = ct = calls = 0
    for name in ("llm_cache.sqlite", "tool_cache.sqlite"):
        a, b, n = _cache_usage(run_dir / name)
        pt, ct, calls = pt + a, ct + b, calls + n
    secs = 0.0
    db = run_dir / "ledger.sqlite"
    if db.exists() and db.stat().st_size:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            bodies = [json.loads(b) for (b,) in c.execute("SELECT body FROM evidence ORDER BY seq")]
        except sqlite3.DatabaseError:
            bodies = []
        finally:
            c.close()
        if bodies:
            first = datetime.fromisoformat(bodies[0]["started_at"])
            last = datetime.fromisoformat(bodies[-1]["ended_at"])
            secs = (last - first).total_seconds()
    return {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "llm_calls": calls,
        "wall_clock_s": secs,
        "gpu_hours_est": secs / 3600,
    }
