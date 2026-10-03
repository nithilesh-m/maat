from __future__ import annotations

import hashlib
import json
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
import pandas as pd
from pydantic import BaseModel

from maat.options import AuditOptions


class Condition(BaseModel):
    name: str
    options: AuditOptions


class MatrixConfig(BaseModel):
    name: str
    systems: list[str]
    conditions: list[Condition]
    repeats: int = 1
    llm_mode: Literal["live", "record"] = "live"

    def hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:16]


class Cell(BaseModel):
    cell_id: str
    system: str
    condition: str
    repeat: int


def cells(cfg: MatrixConfig) -> list[Cell]:
    out = []
    for s in cfg.systems:
        stem = Path(s).stem
        for c in cfg.conditions:
            for r in range(cfg.repeats):
                out.append(
                    Cell(cell_id=f"{stem}__{c.name}__r{r}", system=s, condition=c.name, repeat=r)
                )
    return out


def model_digests(base_url: str = "http://localhost:11434") -> str:
    """Digests of the models Ollama has pulled, or "unavailable" if it cannot be reached."""
    try:
        tags = httpx.get(f"{base_url}/api/tags", timeout=5).json()["models"]
        return json.dumps({m["name"]: m["digest"][:12] for m in tags}, sort_keys=True)
    except (httpx.HTTPError, KeyError, ValueError):
        return "unavailable"


def run_matrix(
    cfg: MatrixConfig, out_dir: Path, executor: Callable[[Cell, Path], dict] | None = None
) -> pd.DataFrame:
    """Run every cell, never aborting on a failure. Cells already `complete` in index.csv are
    skipped, so an interrupted or partly failed matrix can simply be run again."""
    if executor is None:
        from experiments.run_matrix import execute_cell

        def executor(cell: Cell, out: Path) -> dict:
            return execute_cell(cfg, cell, out)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    idx_path = out_dir / "index.csv"
    done: set[str] = set()
    rows: list[dict] = []
    if idx_path.exists():
        prev = pd.read_csv(idx_path)
        stale = set(prev[prev.status == "complete"].config_hash.astype(str)) - {cfg.hash()}
        if stale:
            raise ValueError(
                f"{idx_path} was produced with a different config ({sorted(stale)}); "
                "start a new output directory instead of mixing configurations"
            )
        done = set(prev[prev.status == "complete"].cell_id)
        rows = [r for r in prev.to_dict("records") if r["cell_id"] in done]
    digests = model_digests()
    for cell in cells(cfg):
        if cell.cell_id in done:
            continue
        stale_dir = out_dir / "runs" / f"{cfg.name}-{cell.cell_id}"
        if stale_dir.exists():  # a failed attempt left its run dir; keep it, free the name
            (out_dir / "failed").mkdir(exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
            stale_dir.rename(out_dir / "failed" / f"{stale_dir.name}-{stamp}")
        row = {
            **cell.model_dump(),
            "config_hash": cfg.hash(),
            "model_digests": digests,
            "started": datetime.now(UTC).isoformat(),
            "run_id": None,
            "run_dir": None,
            "bundle_id": None,
            "status": "failed",
            "error": None,
        }
        try:
            row.update(executor(cell, out_dir))
            row["status"] = "complete"
        except Exception as e:  # noqa: BLE001 - recorded, the matrix continues
            row["error"] = f"{type(e).__name__}: {e}"
            (out_dir / "errors").mkdir(exist_ok=True)
            (out_dir / "errors" / f"{cell.cell_id}.txt").write_text(traceback.format_exc())
        row["ended"] = datetime.now(UTC).isoformat()
        rows.append(row)
        pd.DataFrame(rows).to_csv(idx_path, index=False)
    return pd.DataFrame(rows)
