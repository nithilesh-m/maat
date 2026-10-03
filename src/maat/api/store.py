from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path


class RunStore:
    def __init__(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._c = sqlite3.connect(path, check_same_thread=False)
        self._c.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._c.execute(
            "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, run_dir TEXT, profile TEXT, "
            "planner TEXT, created_by TEXT, created_at TEXT, status TEXT, error TEXT)"
        )

    def create(self, run_id, run_dir, profile_path, planner, created_by) -> None:
        with self._lock, self._c:
            self._c.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    str(run_dir),
                    str(profile_path),
                    planner,
                    created_by,
                    datetime.now(UTC).isoformat(),
                    "queued",
                    None,
                ),
            )

    def set_status(self, run_id, status, error=None) -> None:
        with self._lock, self._c:
            self._c.execute(
                "UPDATE runs SET status=?, error=? WHERE run_id=?", (status, error, run_id)
            )

    def get(self, run_id) -> dict | None:
        r = self._c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(r) if r else None

    def list(self, limit: int = 50, offset: int = 0) -> list[dict]:
        return [
            dict(r)
            for r in self._c.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
            )
        ]

    def fail_incomplete(self, reason: str) -> int:
        """Mark runs left queued/running by a previous process as failed (paused runs resume)."""
        with self._lock, self._c:
            cur = self._c.execute(
                "UPDATE runs SET status='failed', error=? WHERE status IN ('queued','running')",
                (reason,),
            )
            return cur.rowcount
