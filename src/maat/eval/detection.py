from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel

from maat.evidence.bundle import read_bundle
from maat.schemas.findings import FindingStatus

FLAG = {"block", "fail", "waive"}


class Defect(BaseModel):
    id: str
    testbed: str
    variant: str
    split: str
    description: str
    controls: list[str]


def load_defects(path: Path, split: str, final: bool = False) -> list[Defect]:
    """The test split is reserved for final RQ1 numbers (Review Focus #5): asking for it, or for
    "all", without `final=True` is an error so tuning can never touch it by accident."""
    if split in ("test", "all") and not final:
        raise ValueError(
            "test-split defects are for final RQ1 numbers only; pass --final to use them"
        )
    ds = [Defect.model_validate(d) for d in yaml.safe_load(Path(path).read_text())]
    return ds if split == "all" else [d for d in ds if d.split == split]


def flagged_controls(run_dir: str) -> set[str]:
    b = read_bundle(Path(run_dir))
    out = {d.clause_id for d in b.decisions if d.outcome.value in FLAG}
    out |= {c for f in b.findings if f.status is not FindingStatus.DISPUTED for c in f.clause_ids}
    return out


def _parse(cell_id: str) -> tuple[str, str]:
    system = cell_id.split("__")[0]  # e.g. t1_seeded
    testbed, variant = system.rsplit("_", 1)  # t1, seeded
    return testbed, variant


def detection_scores(
    index: pd.DataFrame,
    defects: list[Defect],
    flagged_of: Callable[[str], set[str]] = flagged_controls,
) -> pd.DataFrame:
    """Per (condition, testbed, repeat): TP = planted defects with a flagged control, FN = the
    rest, FP = flagged controls in the *clean* run of the same cell that are under test."""
    ok = index[index.status == "complete"]
    runs: dict[tuple, set[str]] = {}
    for r in ok.itertuples():
        tb, var = _parse(r.cell_id)
        runs[(r.condition, tb, var, r.repeat)] = flagged_of(r.run_dir)
    rows = []
    for (cond, tb, var, rep), flagged in runs.items():
        if var != "seeded":
            continue
        mine = [d for d in defects if d.testbed == tb]
        tp = sum(1 for d in mine if set(d.controls) & flagged)
        fn = len(mine) - tp
        under_test = {c for d in mine for c in d.controls}
        twin = (cond, tb, "clean", rep)
        clean_missing = twin not in runs  # a failed/absent clean run must not read as "no FPs"
        fp = len(runs.get(twin, set()) & under_test)
        p = float("nan") if clean_missing else (tp / (tp + fp) if tp + fp else 0.0)
        rcl = tp / (tp + fn) if tp + fn else 0.0
        rows.append(
            {
                "condition": cond,
                "testbed": tb,
                "repeat": rep,
                "tp": tp,
                "fn": fn,
                "fp": fp,
                "precision": p,
                "recall": rcl,
                "f1": 2 * p * rcl / (p + rcl)
                if p + rcl and p == p
                else float("nan")
                if p != p
                else 0.0,
                "clean_missing": clean_missing,
                "caught": ",".join(d.id for d in mine if set(d.controls) & flagged),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_ci(
    values: list[float], n: int = 2000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, float)
    means = [rng.choice(arr, len(arr), replace=True).mean() for _ in range(n)]
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))
