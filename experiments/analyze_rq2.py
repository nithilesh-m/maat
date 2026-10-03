"""RQ2 analysis: run-to-run flip rate and judge-perturbation sensitivity.

    uv run python -m experiments.analyze_rq2 --index experiments/results/rq2/index.csv \
        --out experiments/results/rq2/
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import pandas as pd

from maat.eval.stability import flip_rate, perturb_judgments
from maat.evidence.bundle import read_bundle


def analyze(index_path: Path, out: Path, judges, qual_gate: Path | None = None) -> pd.DataFrame:
    idx = pd.read_csv(index_path)
    idx = idx[idx.status == "complete"]
    out.mkdir(parents=True, exist_ok=True)
    flips, perturbs = [], []
    for system, g in idx.groupby(idx.cell_id.str.split("__").str[0]):
        runs = [Path(r) for r in g.run_dir]
        flips.append(flip_rate([read_bundle(r) for r in runs]).assign(system=system))
        perturbs.append(perturb_judgments(runs[0], judges).assign(system=system))
    flip = pd.concat(flips, ignore_index=True) if flips else pd.DataFrame()
    pert = pd.concat(perturbs, ignore_index=True) if perturbs else pd.DataFrame()
    flip.to_csv(out / "rq2_flip.csv", index=False)
    pert.to_csv(out / "rq2_perturb.csv", index=False)
    rows = []
    if not flip.empty:
        for method, g in flip.groupby("method"):
            rows.append(
                {"metric": f"flip_rate_{method}", "value": float(g.flipped.mean()), "n": len(g)}
            )
    if not pert.empty:
        for kind, g in pert.groupby("kind"):
            rows.append(
                {
                    "metric": f"perturb_change_rate_{kind}",
                    "value": float(g.changed.mean()),
                    "n": len(g),
                }
            )
    if qual_gate and Path(qual_gate).exists():
        q = json.loads(Path(qual_gate).read_text())
        for k in ("kappa_vs_gold", "alpha_judges", "abstention_rate", "flip_rate"):
            if q.get(k) is not None:
                rows.append({"metric": f"qual_gate_{k}", "value": q[k], "n": q.get("n")})
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "rq2_summary.csv", index=False)
    return summary


if __name__ == "__main__":
    from maat.config import load_config
    from maat.llm.cache import LLMCache
    from maat.llm.client import get_judges

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--qual-gate", type=Path, default=Path("experiments/results/qual_gate.json"))
    a = ap.parse_args()
    cfg = load_config()
    cfg.llm_mode = "live"
    with tempfile.TemporaryDirectory() as td:
        panel = get_judges(cfg, LLMCache(Path(td) / "c.sqlite", "live"))
        print(analyze(a.index, a.out, panel, a.qual_gate).to_markdown(index=False))
