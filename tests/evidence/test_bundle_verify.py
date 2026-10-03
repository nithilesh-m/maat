import base64
import json
import shutil
import sqlite3

import pytest

from maat.evidence.artifacts import ArtifactStore
from maat.evidence.bundle import BUNDLE_FILE, build_bundle, merkle_root, read_bundle, write_bundle
from maat.evidence.canonical import sha256_hex
from maat.evidence.ledger import Ledger
from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from maat.schemas.evidence import EvidenceDraft
from tests.fakes import AS_OF, SEED, seq_ids

KEY = RunKey.from_seed(SEED)


def make_run(run_dir):
    run_dir.mkdir()
    led = Ledger(run_dir / "ledger.sqlite", "run-1", KEY, seq_ids())
    art = ArtifactStore(run_dir / "artifacts", "run-1").put_json({"o": 1}, "risk", "o.json")
    for i in range(3):
        led.append(
            EvidenceDraft(
                run_id="run-1",
                agent="risk",
                tool="probe_prompt_injection@1.0.0",
                evidence_type="measured",
                target_ref="t@sha256:x",
                result={"metrics": {"asr": i / 10}, "samples": []},
                artifacts=[art] if i == 0 else [],
                started_at=AS_OF,
                ended_at=AS_OF,
            )
        )
    records = led.records()
    led.close()
    b = build_bundle(
        run_id="run-1",
        target_ref="t@sha256:x",
        tier="limited",
        regimes=["EU"],
        versions={"catalog": "c", "policies": "p"},
        created_at=AS_OF,
        records=records,
        decisions=[],
        clause_ids_by_tool={"probe_prompt_injection": ["VG-SEC-01"]},
    )
    write_bundle(b, run_dir, KEY)
    return b


def test_merkle_root_known_values():
    e = "sha256:" + sha256_hex(b"")
    assert merkle_root([]) == e
    h = "sha256:" + "ab" * 32
    assert merkle_root([h]) == h
    assert merkle_root([h, h, h]) == merkle_root([h, h, h, h])  # odd level duplicates last


def test_roundtrip_and_verify_ok(tmp_path):
    b = make_run(tmp_path / "run")
    assert read_bundle(tmp_path / "run") == b
    assert b.entries[0].clause_ids == ["VG-SEC-01"]
    rep = verify_run(tmp_path / "run", expected_pubkeys=[KEY.public_key_b64])
    assert rep.ok, rep.problems
    assert rep.records == 3 and rep.bundle_id == b.header.bundle_id


def _tamper_sql(run, sql):
    c = sqlite3.connect(run / "ledger.sqlite")
    c.execute("DROP TRIGGER evidence_no_update")
    c.execute("DROP TRIGGER evidence_no_delete")
    c.execute(sql)
    c.commit()
    c.close()


def test_altered_record_detected(tmp_path):
    make_run(tmp_path / "run")
    _tamper_sql(
        tmp_path / "run",
        "UPDATE evidence SET body = replace(body, '\"asr\":0.1', '\"asr\":0.0') WHERE seq=1",
    )
    rep = verify_run(tmp_path / "run")
    assert not rep.ok and any("content altered" in p for p in rep.problems)


def test_deleted_record_detected(tmp_path):
    make_run(tmp_path / "run")
    _tamper_sql(tmp_path / "run", "DELETE FROM evidence WHERE seq=1")
    rep = verify_run(tmp_path / "run")
    assert not rep.ok and any("chain" in p or "do not match" in p for p in rep.problems)


def test_edited_decisions_break_signature(tmp_path):
    make_run(tmp_path / "run")
    p = tmp_path / "run" / BUNDLE_FILE
    env = json.loads(p.read_text())
    stmt = json.loads(base64.b64decode(env["payload"]))
    stmt["predicate"]["status"] = "incomplete"
    env["payload"] = base64.b64encode(json.dumps(stmt).encode()).decode()
    p.write_text(json.dumps(env))
    rep = verify_run(tmp_path / "run")
    assert not rep.ok and any("signature" in p for p in rep.problems)


def test_tampered_artifact_detected(tmp_path):
    make_run(tmp_path / "run")
    f = next((tmp_path / "run" / "artifacts").iterdir())
    f.write_bytes(b"tampered")
    rep = verify_run(tmp_path / "run")
    assert not rep.ok and any("artifact" in p for p in rep.problems)


def test_unexpected_signer(tmp_path):
    make_run(tmp_path / "run")
    other = RunKey.from_seed(b"\x09" * 32).public_key_b64
    rep = verify_run(tmp_path / "run", expected_pubkeys=[other])
    assert not rep.ok and any("unexpected signer" in p for p in rep.problems)


# Review Focus #5
@pytest.mark.parametrize(
    "breakage", ["missing_dir", "missing_bundle", "garbage_json", "missing_ledger"]
)
def test_broken_run_dirs_report_not_raise(tmp_path, breakage):
    run = tmp_path / "run"
    if breakage != "missing_dir":
        make_run(run)
    if breakage == "missing_bundle":
        (run / BUNDLE_FILE).unlink()
    if breakage == "garbage_json":
        (run / BUNDLE_FILE).write_text("{not json")
    if breakage == "missing_ledger":
        (run / "ledger.sqlite").unlink()
    rep = verify_run(run)
    assert not rep.ok and rep.problems


def test_read_bundle_malformed_is_value_error(tmp_path):
    make_run(tmp_path / "run")
    (tmp_path / "run" / BUNDLE_FILE).write_text('{"payload": "!!"}')
    with pytest.raises(ValueError):
        read_bundle(tmp_path / "run")


def test_copied_run_still_verifies(tmp_path):
    make_run(tmp_path / "run")
    shutil.copytree(tmp_path / "run", tmp_path / "copy")
    assert verify_run(tmp_path / "copy").ok
