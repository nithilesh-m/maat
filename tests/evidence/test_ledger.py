import sqlite3
from datetime import UTC, datetime

import pytest

from maat.evidence.canonical import digest
from maat.evidence.ledger import GENESIS, Ledger, LedgerError
from maat.evidence.signing import RunKey, verify_signature
from maat.schemas.evidence import EvidenceDraft, EvidenceType

T0 = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)


def draft(run_id="run-1", n=0):
    return EvidenceDraft(
        run_id=run_id,
        agent="risk",
        tool="probe_prompt_injection@1.0.0",
        evidence_type=EvidenceType.MEASURED,
        target_ref="bot@sha256:aa",
        params={"split": "dev"},
        result={"metrics": {"asr": 0.25 + n}, "samples": []},
        started_at=T0,
        ended_at=T0,
    )


def make(tmp_path, ids=None):
    it = iter(ids or [f"rec-{i}" for i in range(100)])
    return Ledger(
        tmp_path / "ledger.sqlite",
        "run-1",
        RunKey.from_seed(b"\x02" * 32),
        id_factory=lambda: next(it),
    )


def test_append_builds_hash_chain(tmp_path):
    led = make(tmp_path)
    r0 = led.append(draft(n=0))
    r1 = led.append(draft(n=1))
    assert r0.seq == 0 and r0.prev_hash == GENESIS
    assert r1.seq == 1 and r1.prev_hash == r0.hash
    assert digest(r1.hash_payload()) == r1.hash
    assert verify_signature(r1.signer, r1.hash.encode(), r1.sig)
    assert [r.id for r in led.records()] == ["rec-0", "rec-1"]


def test_records_roundtrip_exactly(tmp_path):
    led = make(tmp_path)
    r = led.append(draft())
    assert led.records()[0] == r


def test_ledger_rejects_update_and_delete(tmp_path):
    led = make(tmp_path)
    led.append(draft())
    led.close()
    conn = sqlite3.connect(tmp_path / "ledger.sqlite")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE evidence SET body = '{}' WHERE seq = 0")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM evidence")


def test_wrong_run_id_rejected(tmp_path):
    with pytest.raises(LedgerError, match="run_id"):
        make(tmp_path).append(draft(run_id="other-run"))


def test_reopen_continues_chain(tmp_path):
    led = make(tmp_path, ids=["a", "b"])
    r0 = led.append(draft())
    led.close()
    led2 = Ledger(
        tmp_path / "ledger.sqlite", "run-1", RunKey.from_seed(b"\x03" * 32), id_factory=lambda: "c"
    )
    r1 = led2.append(draft(n=1))
    assert r1.seq == 1 and r1.prev_hash == r0.hash
    assert r1.signer != r0.signer  # a different key may append (e.g. a reviewer)


def test_closed_ledger_is_single_file_and_close_is_idempotent(tmp_path):
    led = make(tmp_path)
    led.append(draft())
    led.close()
    led.close()
    assert not (tmp_path / "ledger.sqlite-wal").exists()
