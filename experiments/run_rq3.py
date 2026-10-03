"""RQ3: apply mitigations to the seeded systems, re-test on held-out probes, report the effect.

    uv run python -m experiments.run_rq3 --index experiments/results/rq3/index.csv \
        --out experiments/results/rq3/
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from maat.catalog.loader import load_catalog
from maat.eval.matrix import Cell  # noqa: F401  (documented dependency of the index format)
from maat.eval.remediation_eval import remediation_rows, utility_rows
from maat.profile.loader import load_profile
from maat.service import remediate_run


def _one(r, catalog, config, target_builder, controls, utility, summary) -> None:
    testbed = r.cell_id.split("__")[0].rsplit("_", 1)[0]
    prof = load_profile(Path(r.system)).model_copy(update={"sandbox_allowed": True})
    res = remediate_run(
        Path(r.run_dir), prof, apply=True, config=config, target_builder=target_builder
    )
    if res.child_dir is None:
        return  # nothing automatic applied to this run
    rows = [
        {**x, "cell_id": r.cell_id, "testbed": testbed, "sandbox_override": True}
        for x in remediation_rows(Path(r.run_dir), res.child_dir, catalog)
    ]
    controls += rows
    u = utility_rows(res.child_dir)
    utility.append({**u, "cell_id": r.cell_id, "testbed": testbed})
    mitigated = [
        x for x in rows if x["regime"] == "EU" and x["before_outcome"] in ("block", "fail")
    ]
    flipped = [x for x in mitigated if x["after_outcome"] == "pass"]
    summary.append(
        {
            "testbed": testbed,
            "cell_id": r.cell_id,
            **{k: res.summary.get(k) for k in ("AS_before", "AS_after", "delta_AS")},
            "n_mitigated_controls": len(mitigated),
            "share_flipped_to_pass": len(flipped) / len(mitigated) if mitigated else None,
            "utility_delta": u["delta"],
        }
    )


def run(
    index_path: Path, out: Path, target_builder=None, config: Path | None = None
) -> pd.DataFrame:
    idx = pd.read_csv(index_path)
    idx = idx[(idx.status == "complete") & idx.cell_id.str.contains("_seeded__")]
    catalog = load_catalog()
    out.mkdir(parents=True, exist_ok=True)
    controls, utility, summary = [], [], []
    errors = []
    for r in idx.itertuples():
        try:
            _one(r, catalog, config, target_builder, controls, utility, summary)
        except Exception as e:  # noqa: BLE001 - recorded; the other cells still run
            errors.append({"cell_id": r.cell_id, "error": f"{type(e).__name__}: {e}"})
    pd.DataFrame(errors, columns=["cell_id", "error"]).to_csv(out / "rq3_errors.csv", index=False)
    pd.DataFrame(controls).to_csv(out / "rq3_controls.csv", index=False)
    pd.DataFrame(utility).to_csv(out / "rq3_utility.csv", index=False)
    s = pd.DataFrame(summary)
    if not s.empty:
        s = (
            s.groupby("testbed")
            .agg(
                delta_AS=("delta_AS", "mean"),
                share_flipped_to_pass=("share_flipped_to_pass", "mean"),
                median_utility_delta=("utility_delta", "median"),
                n_runs=("cell_id", "count"),
            )
            .reset_index()
        )
    s.to_csv(out / "rq3_summary.csv", index=False)
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    print(run(a.index, a.out, config=Path("maat.toml")).to_markdown(index=False))
