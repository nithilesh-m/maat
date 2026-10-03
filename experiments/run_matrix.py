"""Run an experiment matrix.

Usage:
    uv run python -m experiments.run_matrix \
        experiments/configs/rq1_detection.yaml experiments/results/rq1
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from maat.config import load_config
from maat.eval.matrix import Cell, MatrixConfig, run_matrix
from maat.evidence.signing import RunKey
from maat.llm.untrusted import PromptGuardScreen
from maat.profile.loader import load_profile
from maat.runner import RunConfig
from maat.service import build_target, execute_audit


def execute_cell(cfg: MatrixConfig, cell: Cell, out: Path) -> dict:
    prof = load_profile(Path(cell.system))
    maat_cfg = load_config()
    maat_cfg.llm_mode = cfg.llm_mode
    cond = next(c for c in cfg.conditions if c.name == cell.condition)
    run_id = f"{cfg.name}-{cell.cell_id}"
    now = datetime.now(UTC)
    rc = RunConfig(
        run_id=run_id,
        run_dir=out / "runs" / run_id,
        signer=RunKey.generate(),
        as_of=now,
        meta={
            "run_id": run_id,
            "as_of": now.isoformat(),
            "planner": cond.options.planner,
            "options": cond.options.model_dump(),
            "condition": cond.name,
            "cell": cell.model_dump(),
        },
    )
    b = execute_audit(
        prof, build_target(prof), rc, maat_cfg, cond.options, PromptGuardScreen(), auto_approve=True
    )
    return {"run_id": run_id, "run_dir": str(rc.run_dir), "bundle_id": b.header.bundle_id}


if __name__ == "__main__":
    cfg = MatrixConfig.model_validate(yaml.safe_load(Path(sys.argv[1]).read_text()))
    df = run_matrix(cfg, Path(sys.argv[2]))
    print(df.groupby(["condition", "status"]).size())
