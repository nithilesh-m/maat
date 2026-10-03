"""RQ4: evidence quality (CC/AS/MER/RF), tamper detection, replay determinism and cost.

    uv run python -m experiments.run_rq4 --index experiments/results/rq4/index.csv \
        --out experiments/results/rq4/ [--cost-index experiments/results/rq1/index.csv]
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pandas as pd

from maat.catalog.loader import load_catalog
from maat.eval.cost import cost_rows
from maat.eval.quality import quality_rows, replay_check, tamper_trials


def _complete(index_path: Path) -> pd.DataFrame:
    idx = pd.read_csv(index_path)
    return idx[idx.status == "complete"]


def run(index_path: Path, out: Path, cost_index: Path | None = None, trials: int = 50) -> dict:
    catalog = load_catalog()
    out.mkdir(parents=True, exist_ok=True)
    quality, tamper, replay, cost = [], [], [], []
    for r in _complete(index_path).itertuples():
        run_dir = Path(r.run_dir)
        for reg, m in quality_rows(run_dir, catalog).items():
            quality.append({"cell_id": r.cell_id, "condition": r.condition, "regime": reg, **m})
        tamper.append(
            tamper_trials(run_dir, n=trials).assign(cell_id=r.cell_id, condition=r.condition)
        )
        # Replays are full run directories (artifacts, LLM cache): keep them out of the results.
        with tempfile.TemporaryDirectory() as td:
            res = replay_check(run_dir, Path(td))
        replay.append({"cell_id": r.cell_id, "condition": r.condition, **res})
    cost_src = [_complete(index_path)] + ([_complete(cost_index)] if cost_index else [])
    for df in cost_src:
        for r in df.itertuples():
            cost.append(
                {"cell_id": r.cell_id, "condition": r.condition, **cost_rows(Path(r.run_dir))}
            )
    frames = {
        "rq4_quality.csv": pd.DataFrame(quality),
        "rq4_tamper.csv": pd.concat(tamper, ignore_index=True) if tamper else pd.DataFrame(),
        "rq4_replay.csv": pd.DataFrame(replay),
        "rq4_cost.csv": pd.DataFrame(cost).drop_duplicates("cell_id") if cost else pd.DataFrame(),
    }
    for name, df in frames.items():
        df.to_csv(out / name, index=False)
    detected = frames["rq4_tamper.csv"]
    return {
        "tamper_detection_rate": float(detected.detected.mean()) if len(detected) else None,
        "replay_match_rate": float(frames["rq4_replay.csv"].match.mean()) if replay else None,
        "n_cells": len(replay),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cost-index", type=Path, default=None)
    a = ap.parse_args()
    print(run(a.index, a.out, a.cost_index))
