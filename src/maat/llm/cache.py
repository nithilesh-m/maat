from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Literal

Mode = Literal["live", "record", "replay"]


class CacheMiss(LookupError):
    pass


class LLMCache:
    def __init__(self, path: Path, mode: Mode = "record") -> None:
        self.mode = mode
        self._conn = sqlite3.connect(Path(path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS llm_cache "
            "(key TEXT PRIMARY KEY, request TEXT NOT NULL, response TEXT NOT NULL)"
        )

    def get(self, key: str) -> dict | None:
        row = self._conn.execute("SELECT response FROM llm_cache WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, request: dict, response: dict) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO llm_cache VALUES (?, ?, ?)",
                (key, json.dumps(request), json.dumps(response)),
            )
