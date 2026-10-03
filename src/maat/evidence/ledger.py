from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

from ulid import ULID

from maat.evidence.canonical import digest
from maat.evidence.signing import RunKey
from maat.schemas.evidence import EvidenceDraft, EvidenceRecord

GENESIS = "sha256:" + "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
  seq INTEGER PRIMARY KEY,
  id TEXT NOT NULL UNIQUE,
  run_id TEXT NOT NULL,
  body TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS evidence_no_update BEFORE UPDATE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence ledger is append-only'); END;
"""


class LedgerError(RuntimeError):
    pass


class Ledger:
    """Append-only, hash-chained, signed evidence ledger (SQLite)."""

    def __init__(
        self,
        path: Path,
        run_id: str,
        signer: RunKey,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self._signer = signer
        self._new_id = id_factory or (lambda: str(ULID()))
        self._closed = False
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)

    def append(self, draft: EvidenceDraft) -> EvidenceRecord:
        if draft.run_id != self.run_id:
            raise LedgerError(f"draft run_id {draft.run_id!r} != ledger run_id {self.run_id!r}")
        last = self._conn.execute(
            "SELECT seq, body FROM evidence ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        seq = 0 if last is None else last[0] + 1
        prev_hash = GENESIS if last is None else json.loads(last[1])["hash"]
        payload = {
            **draft.model_dump(mode="json"),
            "id": self._new_id(),
            "seq": seq,
            "prev_hash": prev_hash,
        }
        # The signer key is bound by the signature, not by the hash, so a replay signed
        # with a different key reproduces identical record hashes and bundle_id.
        h = digest(payload)
        record = EvidenceRecord.model_validate(
            {
                **payload,
                "signer": self._signer.public_key_b64,
                "hash": h,
                "sig": self._signer.sign(h.encode()),
            }
        )
        with self._conn:
            self._conn.execute(
                "INSERT INTO evidence(seq, id, run_id, body) VALUES (?, ?, ?, ?)",
                (seq, record.id, self.run_id, record.model_dump_json()),
            )
        return record

    def records(self) -> list[EvidenceRecord]:
        rows = self._conn.execute("SELECT body FROM evidence ORDER BY seq").fetchall()
        return [EvidenceRecord.model_validate_json(b) for (b,) in rows]

    def close(self) -> None:
        """Idempotent. Leaves a single self-contained SQLite file (no -wal/-shm)."""
        if self._closed:
            return
        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._conn.execute("PRAGMA journal_mode=DELETE")
        self._conn.close()
        self._closed = True
