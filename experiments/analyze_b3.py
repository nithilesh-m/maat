"""Score the manual B3 baseline with the same detection logic as every other condition.

    uv run python -m experiments.analyze_b3 --sheet docs/experiments/manual_b3_sheet.csv \
        --split dev --out experiments/results/b3.csv

A control counts as flagged when the auditor labelled it N or P. The test split needs --final.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from maat.eval.detection import detection_scores, load_defects

FLAGGING = {"N", "P"}


def analyze_b3(
    sheet: Path, defects_path: Path, split: str = "dev", final: bool = False
) -> pd.DataFrame:
    defects = load_defects(defects_path, split, final=final)
    df = pd.read_csv(sheet)
    auditors = sorted(df.auditor.unique())
    flagged: dict[str, set[str]] = {}
    rows = []
    for rep, auditor in enumerate(auditors):  # each auditor is one "repeat" of the condition
        for system, g in df[df.auditor == auditor].groupby("system"):
            key = f"{system}__b3__r{rep}"
            flagged[key] = set(g[g.label.isin(FLAGGING)].control_id)
            rows.append(
                {
                    "cell_id": key,
                    "condition": "b3",
                    "repeat": rep,
                    "status": "complete",
                    "run_dir": key,
                }
            )
    return detection_scores(pd.DataFrame(rows), defects, flagged_of=lambda k: flagged[k])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--sheet", type=Path, default=Path("docs/experiments/manual_b3_sheet.csv"))
    ap.add_argument("--defects", type=Path, default=Path("testbed/defects.yaml"))
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    result = analyze_b3(a.sheet, a.defects, a.split, a.final).assign(
        split_used=a.split, final=a.final
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(a.out, index=False)
    print(result.to_markdown(index=False))
