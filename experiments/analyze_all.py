"""Run every RQ analysis and write the frozen paper artifacts.

    uv run python -m experiments.analyze_all --results experiments/results \
        --out experiments/results/final [--split test --final]
    uv run python -m experiments.freeze --dir experiments/results/final --check

An RQ whose index.csv is missing is skipped and listed in tables.md, so a partial run still
produces a consistent, checkable result set.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from experiments import plots
from experiments.freeze import write_manifest


def _failed_cells(results: Path) -> pd.DataFrame:
    frames = []
    for idx in sorted(results.glob("rq*/index.csv")):
        df = pd.read_csv(idx)
        bad = df[df.status != "complete"]
        if len(bad):
            frames.append(bad.assign(rq=idx.parent.name)[["rq", "cell_id", "condition", "error"]])
    if not frames:
        return pd.DataFrame(columns=["rq", "cell_id", "condition", "error"])
    return pd.concat(frames, ignore_index=True)


def analyze_all(
    results: Path,
    out: Path,
    defects: Path = Path("testbed/defects.yaml"),
    split: str = "dev",
    final_flag: bool = False,
    judges=None,
    qual_gate: Path | None = None,
) -> Path:
    results, out = Path(results), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    skipped: list[str] = []
    sources: dict[str, str] = {}

    errors: list[dict] = []

    def guarded(rq: str, fn) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - one failing analysis must not lose the others
            errors.append({"rq": rq, "error": f"{type(e).__name__}: {e}"})

    rq1 = results / "rq1" / "index.csv"
    if rq1.exists():

        def do1():
            from experiments.analyze_rq1 import analyze

            analyze(rq1, defects, split, final_flag, out)
            sources["rq1_by_condition.csv"] = sources["rq1_per_defect.csv"] = "rq1/index.csv"

        guarded("rq1", do1)
    else:
        skipped.append("rq1")

    rq2 = results / "rq2" / "index.csv"
    if rq2.exists():

        def do2():
            from experiments.analyze_rq2 import analyze as analyze2

            panel = judges
            if panel is None:
                from maat.config import load_config
                from maat.llm.cache import LLMCache
                from maat.llm.client import get_judges

                cfg = load_config()
                cfg.llm_mode = "live"
                panel = get_judges(cfg, LLMCache(out / ".judge_cache.sqlite", "live"))
            analyze2(rq2, out, panel, qual_gate or results / "qual_gate.json")
            for n in ("rq2_flip.csv", "rq2_perturb.csv", "rq2_summary.csv"):
                sources[n] = "rq2/index.csv"

        guarded("rq2", do2)
    else:
        skipped.append("rq2")

    rq3 = results / "rq3" / "index.csv"
    if rq3.exists():

        def do3():
            # Remediation applies mitigations to live targets: do it once (run_rq3), and let the
            # analysis only read its results, so re-analysing never changes the numbers.
            names = ("rq3_controls.csv", "rq3_utility.csv", "rq3_summary.csv")
            if not all((rq3.parent / n).exists() for n in names):
                import experiments.run_rq3 as run_rq3

                run_rq3.run(rq3, rq3.parent, config=Path("maat.toml"))
            for n in names:
                shutil.copy2(rq3.parent / n, out / n)
                sources[n] = "rq3/index.csv"

        guarded("rq3", do3)
    else:
        skipped.append("rq3")

    rq4 = results / "rq4" / "index.csv"
    if rq4.exists():

        def do4():
            from experiments.run_rq4 import run as run4

            run4(rq4, out, cost_index=rq1 if rq1.exists() else None)
            for n in ("rq4_quality.csv", "rq4_tamper.csv", "rq4_replay.csv", "rq4_cost.csv"):
                sources[n] = "rq4/index.csv"

        guarded("rq4", do4)
    else:
        skipped.append("rq4")

    if errors:
        pd.DataFrame(errors).to_csv(out / "analysis_errors.csv", index=False)

    failed = _failed_cells(results)
    failed.to_csv(out / "failed_cells.csv", index=False)

    figs = out / "figures"
    if (out / "rq1_by_condition.csv").exists():
        d = pd.read_csv(out / "rq1_by_condition.csv")
        if len(d):
            plots.bar_with_ci(d, "condition", "f1", "f1_lo", "f1_hi", figs / "rq1_f1")
    if (out / "rq2_flip.csv").exists():
        d = pd.read_csv(out / "rq2_flip.csv")
        if len(d):
            g = d.groupby("method").agg(
                flipped=("flipped", "mean"),
                abstained=("outcomes", lambda s: s.str.contains("abstain").mean()),
            )
            plots.stacked_outcomes(
                g.reset_index().rename(columns={"method": "group"}), figs / "rq2_flip"
            )
    if (out / "rq3_controls.csv").exists():
        d = pd.read_csv(out / "rq3_controls.csv")
        need = {"regime", "metric_before", "metric_after", "control_id"}
        d = (
            d[(d.regime == "EU") & d.metric_before.notna() & d.metric_after.notna()]
            if need <= set(d.columns)
            else d.iloc[0:0]
        )
        if len(d):
            plots.slope(d.drop_duplicates("control_id"), figs / "rq3_slope")
    if (out / "rq4_cost.csv").exists():
        d = pd.read_csv(out / "rq4_cost.csv")
        if len(d):
            plots.box(d, "condition", "gpu_hours_est", figs / "rq4_cost")

    lines = ["# Results tables", "", f"Split used for RQ1: `{split}` (final={final_flag}).", ""]
    for name in sorted(p.name for p in out.glob("*.csv")):
        df = pd.read_csv(out / name)
        src = sources.get(name, "derived")
        lines += [f"## {name}", f"Source: `{src}` → `{name}`", "", df.to_markdown(index=False), ""]
    if skipped:
        lines += ["## Not run", ", ".join(skipped), ""]
    (out / "tables.md").write_text("\n".join(lines))
    (out / ".judge_cache.sqlite").unlink(missing_ok=True)
    write_manifest(out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--results", type=Path, default=Path("experiments/results"))
    ap.add_argument("--out", type=Path, default=Path("experiments/results/final"))
    ap.add_argument("--defects", type=Path, default=Path("testbed/defects.yaml"))
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    print(analyze_all(a.results, a.out, a.defects, a.split, a.final))
