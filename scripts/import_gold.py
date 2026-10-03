"""Import an external annotated dataset (e.g. AIReg-Bench) as MAAT gold-label JSONL.

Inspect the source columns first (`head`), then name them here:

    uv run python scripts/import_gold.py --input data.csv --format csv --id-col id \
        --text-col text --label-col verdict --control-col control \
        --label-map '{"compliant":"S","partially":"P","non-compliant":"N"}' \
        --source aireg-bench --out annotations/gold.jsonl

Rows whose label is not in the map (or not already S/P/N/NA) are skipped and counted on stderr.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from maat.eval.gold import GoldItem

VALID = {"S", "P", "N", "NA"}


def read_rows(path: Path, fmt: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if fmt == "csv":
        return list(csv.DictReader(text.splitlines()))
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--format", choices=["csv", "jsonl"], required=True)
    ap.add_argument("--id-col", required=True)
    ap.add_argument("--text-col", required=True)
    ap.add_argument("--label-col", required=True)
    ap.add_argument("--control-col", required=True)
    ap.add_argument(
        "--label-map", default="{}", help="JSON object mapping source labels to S/P/N/NA"
    )
    ap.add_argument("--source", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    label_map = json.loads(a.label_map)
    items, skipped = [], 0
    for row in read_rows(a.input, a.format):
        raw = str(row.get(a.label_col, "")).strip()
        label = label_map.get(raw, raw if raw in VALID else None)
        if label not in VALID:
            skipped += 1
            continue
        items.append(
            GoldItem(
                id=str(row[a.id_col]),
                control_id=str(row[a.control_col]),
                text=row.get(a.text_col),
                label=label,
                source=a.source,
            )
        )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(i.model_dump_json() + "\n" for i in items), encoding="utf-8")
    print(
        f"imported {len(items)} items; skipped {skipped} rows with unmapped labels", file=sys.stderr
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
