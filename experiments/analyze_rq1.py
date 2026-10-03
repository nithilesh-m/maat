"""RQ1 analysis: detection precision, recall and F1 per condition, with bootstrap CIs.

    uv run python -m experiments.analyze_rq1 --index experiments/results/rq1/index.csv \
        --split test --final --out experiments/results/rq1/

Dev-split analysis needs no flag. Every output row records which split it used and whether
the final flag was set.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from maat.eval.detection import bootstrap_ci, detection_scores, load_defects


def analyze(
    index_path: Path, defects_path: Path, split: str, final: bool, out: Path
) -> pd.DataFrame:
    defects = load_defects(defects_path, split, final=final)
    scores = detection_scores(pd.read_csv(index_path), defects)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for cond, g in scores.groupby("condition"):
        row = {"condition": cond, "n_runs": len(g)}
        for m in ("precision", "recall", "f1"):
            lo, hi = bootstrap_ci(g[m].tolist())
            row.update({m: g[m].mean(), f"{m}_lo": lo, f"{m}_hi": hi})
        rows.append(row)
    by_cond = pd.DataFrame(rows).assign(split_used=split, final=final)
    by_cond.to_csv(out / "rq1_by_condition.csv", index=False)
    per_defect = pd.DataFrame(
        [
            {
                "defect": d.id,
                "testbed": d.testbed,
                "condition": cond,
                "caught_rate": sum(d.id in str(c).split(",") for c in g.caught) / len(g),
            }
            for d in defects
            for cond, g in scores[scores.testbed == d.testbed].groupby("condition")
        ]
    ).assign(split_used=split, final=final)
    per_defect.to_csv(out / "rq1_per_defect.csv", index=False)
    return by_cond


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--defects", type=Path, default=Path("testbed/defects.yaml"))
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument(
        "--final", action="store_true", help="allow the test split (final numbers only)"
    )
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    print(analyze(a.index, a.defects, a.split, a.final, a.out).to_markdown(index=False))
