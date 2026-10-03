from __future__ import annotations

import json
import shutil
import sqlite3
from collections import defaultdict, deque
from pathlib import Path

from maat.evidence.canonical import digest
from maat.schemas.evidence import EvidenceRecord


class ReplayDivergence(RuntimeError):
    pass


class ReplaySource:
    def __init__(self, records: list[EvidenceRecord]) -> None:
        self._q: dict[tuple[str, str], deque[EvidenceRecord]] = defaultdict(deque)
        for r in records:
            self._q[(r.tool, digest(r.params))].append(r)

    def take(self, tool_key: str, params: dict) -> EvidenceRecord:
        q = self._q.get((tool_key, digest(params)))
        if not q:
            raise ReplayDivergence(f"replay diverged: no recorded call {tool_key} {params}")
        return q.popleft()


class ReplayClock:
    def __init__(self, records: list[EvidenceRecord]) -> None:
        self._it = iter([t for r in records for t in (r.started_at, r.ended_at)])

    def __call__(self):
        try:
            return next(self._it)
        except StopIteration as e:
            raise ReplayDivergence("replay diverged: more ledger appends than recorded") from e


class ReplayIds:
    def __init__(self, records: list[EvidenceRecord]) -> None:
        self._it = iter([r.id for r in records])

    def __call__(self) -> str:
        try:
            return next(self._it)
        except StopIteration as e:
            raise ReplayDivergence("replay diverged: more records than recorded") from e


def load_replay(run_dir: Path):
    run_dir = Path(run_dir)
    conn = sqlite3.connect(f"file:{run_dir / 'ledger.sqlite'}?mode=ro", uri=True)
    records = [
        EvidenceRecord.model_validate_json(b)
        for (b,) in conn.execute("SELECT body FROM evidence ORDER BY seq")
    ]
    conn.close()
    meta_p = run_dir / "run_meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    return ReplaySource(records), ReplayClock(records), ReplayIds(records), meta


def copy_replay_inputs(src_run: Path, dst_run: Path) -> None:
    """Copy artifacts and LLM cache so a replay run is self-contained (call after open_run)."""
    src_run, dst_run = Path(src_run), Path(dst_run)
    if (src_run / "artifacts").exists():
        shutil.copytree(src_run / "artifacts", dst_run / "artifacts", dirs_exist_ok=True)
    if (src_run / "llm_cache.sqlite").exists():
        shutil.copy2(src_run / "llm_cache.sqlite", dst_run / "llm_cache.sqlite")
