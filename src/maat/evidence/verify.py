from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from maat.evidence.bundle import BUNDLE_FILE, PAYLOAD_TYPE, merkle_root, pae, read_envelope
from maat.evidence.canonical import digest, sha256_hex
from maat.evidence.ledger import GENESIS
from maat.evidence.signing import verify_signature
from maat.schemas.evidence import EvidenceRecord


@dataclass
class VerifyReport:
    ok: bool
    problems: list[str] = field(default_factory=list)
    bundle_id: str | None = None
    records: int = 0
    redacted: int = 0  # artifacts legitimately absent (signed sensitive and listed to skip)


def verify_run(
    run_dir: Path,
    expected_pubkeys: Iterable[str] | None = None,
    skip_artifacts: Iterable[str] | None = None,
) -> VerifyReport:
    """`skip_artifacts` lists `sha256:` digests whose files were deliberately removed (a redacted
    release). Only those are skipped; every other artifact is still checked."""
    skip = {s.strip() for s in (skip_artifacts or ()) if s.strip()}
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        return VerifyReport(False, [f"run directory not found: {run_dir}"])
    try:
        env, payload, bundle = read_envelope(run_dir)
    except FileNotFoundError:
        return VerifyReport(False, [f"{BUNDLE_FILE} not found in {run_dir}"])
    except json.JSONDecodeError as e:
        return VerifyReport(False, [f"{BUNDLE_FILE} is not valid JSON: {e.msg}"])
    except ValueError as e:
        return VerifyReport(False, [str(e)])

    problems: list[str] = []
    h = bundle.header
    sigs = env.get("signatures") if isinstance(env.get("signatures"), list) else []
    if env.get("payloadType") != PAYLOAD_TYPE:
        problems.append("unexpected payloadType")
    if not any(
        isinstance(s, dict)
        and s.get("keyid") in h.signers
        and verify_signature(s["keyid"], pae(PAYLOAD_TYPE, payload), str(s.get("sig", "")))
        for s in sigs
    ):
        problems.append("bundle signature invalid or signer not listed in header.signers")
    if expected_pubkeys is not None:
        unknown = set(h.signers) - set(expected_pubkeys)
        if unknown:
            problems.append(f"unexpected signer key(s): {sorted(unknown)}")

    ledger = run_dir / "ledger.sqlite"
    if not ledger.exists():
        problems.append("ledger.sqlite not found")
        return VerifyReport(False, problems, h.bundle_id)
    try:
        conn = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
        rows = conn.execute("SELECT seq, body FROM evidence ORDER BY seq").fetchall()
        conn.close()
    except sqlite3.DatabaseError as e:
        problems.append(f"ledger unreadable: {e}")
        return VerifyReport(False, problems, h.bundle_id)

    prev, hashes = GENESIS, []
    skipped = 0
    for i, (seq, body) in enumerate(rows):
        try:
            r = EvidenceRecord.model_validate_json(body)
        except ValidationError:
            problems.append(f"record {seq}: unreadable")
            prev = None
            continue
        if seq != i or r.seq != i:
            problems.append(f"record {seq}: sequence gap (expected {i})")
        if r.prev_hash != prev:
            problems.append(f"record {r.seq}: hash chain broken")
        if digest(r.hash_payload()) != r.hash:
            problems.append(f"record {r.seq}: content altered (hash mismatch)")
        if not verify_signature(r.signer, r.hash.encode(), r.sig):
            problems.append(f"record {r.seq}: invalid signature")
        if r.signer not in h.signers:
            problems.append(f"record {r.seq}: signer not listed in bundle header")
        for a in r.artifacts:
            p = run_dir / "artifacts" / a.sha256.removeprefix("sha256:")
            if not p.exists():
                if (
                    a.sha256 in skip and a.sensitive
                ):  # only a signed-sensitive artifact may be absent
                    skipped += 1
                    continue
                problems.append(f"record {r.seq}: artifact missing {a.uri}")
            elif "sha256:" + sha256_hex(p.read_bytes()) != a.sha256:
                problems.append(f"record {r.seq}: artifact altered {a.uri}")
        prev = r.hash
        hashes.append(r.hash)

    if [e.hash for e in bundle.entries] != hashes:
        problems.append("bundle entries do not match ledger records")
    if merkle_root(hashes) != h.bundle_id:
        problems.append("bundle_id does not match the Merkle root of the ledger")
    return VerifyReport(not problems, problems, h.bundle_id, len(rows), skipped)
