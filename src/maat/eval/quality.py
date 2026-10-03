from __future__ import annotations

import base64
import json
import random
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd

from maat.catalog.c2at import render_view
from maat.catalog.metrics import (
    adequacy_score,
    clause_coverage,
    measured_evidence_ratio,
    reuse_factor,
)
from maat.evidence.bundle import BUNDLE_FILE, read_bundle
from maat.evidence.verify import verify_run
from maat.gates.engine import policy_bundle_version

KINDS = ["record_body", "record_delete", "artifact_bytes", "envelope_payload", "ledger_reorder"]


def quality_rows(run_dir: Path, catalog) -> dict:
    b = read_bundle(run_dir)
    out = {}
    for reg in b.header.regimes:
        rows = render_view(b, catalog, reg, policy_bundle_version())
        if rows:
            out[reg] = {
                "cc": clause_coverage(rows),
                "as": adequacy_score(rows),
                "mer": measured_evidence_ratio(rows, b.entries),
                "rf": reuse_factor(rows),
            }
    return out


def _unlock(db: Path) -> sqlite3.Connection:
    c = sqlite3.connect(db)
    c.execute("DROP TRIGGER IF EXISTS evidence_no_update")
    c.execute("DROP TRIGGER IF EXISTS evidence_no_delete")
    return c


def _mutate(run: Path, kind: str, rng: random.Random) -> bool:
    db = run / "ledger.sqlite"
    if kind in ("record_body", "record_delete", "ledger_reorder"):
        c = _unlock(db)
        rows = c.execute("SELECT seq, body FROM evidence ORDER BY seq").fetchall()
        if len(rows) < 2:
            c.close()
            return False
        if kind == "record_body":
            seq, body = rng.choice(rows)
            d = json.loads(body)
            d["result"]["tampered"] = True
            c.execute("UPDATE evidence SET body=? WHERE seq=?", (json.dumps(d), seq))
        elif kind == "record_delete":
            c.execute("DELETE FROM evidence WHERE seq=?", (rng.choice(rows)[0],))
        else:
            (s1, b1), (s2, b2) = rng.sample(rows, 2)
            c.execute("UPDATE evidence SET body=? WHERE seq=?", (b2, s1))
            c.execute("UPDATE evidence SET body=? WHERE seq=?", (b1, s2))
        c.commit()
        c.close()
        return True
    if kind == "artifact_bytes":
        files = sorted((run / "artifacts").glob("*")) if (run / "artifacts").exists() else []
        if not files:
            return False
        rng.choice(files).write_bytes(b"tampered")
        return True
    env = json.loads((run / BUNDLE_FILE).read_text())
    stmt = json.loads(base64.b64decode(env["payload"]))
    if stmt["predicate"]["decisions"]:
        stmt["predicate"]["decisions"][0]["outcome"] = "pass"
    stmt["predicate"]["status"] = "complete"
    env["payload"] = base64.b64encode(json.dumps(stmt).encode()).decode()
    (run / BUNDLE_FILE).write_text(json.dumps(env))
    return True


def tamper_trials(run_dir: Path, n: int = 50, seed: int = 0) -> pd.DataFrame:
    """Mutate a copy of the run n times (cycling through the mutation kinds) and record whether
    `verify_run` detects each one. The target is 100% detection."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        kind = KINDS[i % len(KINDS)]
        with tempfile.TemporaryDirectory() as td:
            run = Path(td) / "run"
            shutil.copytree(run_dir, run)
            if not _mutate(run, kind, rng):
                continue
            rep = verify_run(run)
            rows.append(
                {"trial": i, "kind": kind, "detected": not rep.ok, "problems": len(rep.problems)}
            )
    return pd.DataFrame(rows)


def replay_check(run_dir: Path, out_dir: Path) -> dict:
    """Replay a run from its ledger and caches; match means the same bundle and decisions."""
    from maat.evidence.bundle import read_bundle as _read
    from maat.service import replay_audit

    try:
        original = _read(run_dir).header.bundle_id
        ok, message = replay_audit(Path(run_dir), Path(out_dir))
    except Exception as e:  # noqa: BLE001 - recorded, not raised
        return {
            "match": False,
            "original": None,
            "replayed": None,
            "error": f"{type(e).__name__}: {e}",
        }
    replayed = message.split()[1] if message.startswith("MATCH") else None
    return {
        "match": ok,
        "original": original,
        "replayed": replayed,
        "error": None if ok else message,
    }
