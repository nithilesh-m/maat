from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path


class EventLog:
    """Append-only JSONL event log for one run (`<dir>/events.jsonl`)."""

    _locks: dict[str, threading.Lock] = {}
    _guard = threading.Lock()

    def __init__(self, directory: Path) -> None:
        self.path = Path(directory) / "events.jsonl"
        with EventLog._guard:
            self._lock = EventLog._locks.setdefault(str(self.path), threading.Lock())

    def append(self, kind: str, payload: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            seq = sum(1 for _ in self.path.open()) if self.path.exists() else 0
            line = {
                "seq": seq,
                "ts": datetime.now(UTC).isoformat(),
                "kind": kind,
                "payload": payload,
            }
            with self.path.open("a") as f:
                f.write(json.dumps(line, default=str) + "\n")

    def read(self, after_seq: int = -1) -> list[dict]:
        if not self.path.exists():
            return []
        with self._lock:
            lines = self.path.read_text().splitlines()
        return [e for e in map(json.loads, lines) if e["seq"] > after_seq]
