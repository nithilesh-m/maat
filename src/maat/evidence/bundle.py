from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from maat.evidence.canonical import canonical_json, sha256_hex
from maat.evidence.signing import RunKey
from maat.schemas.bundle import AuditBundle, BundleEntry, BundleHeader
from maat.schemas.decisions import GateDecision
from maat.schemas.evidence import EvidenceRecord
from maat.schemas.findings import Finding

BUNDLE_FILE = "bundle.dsse.json"
PAYLOAD_TYPE = "application/vnd.in-toto+json"
PREDICATE_TYPE = "https://maat.dev/audit-bundle/v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"


def merkle_root(hashes: list[str]) -> str:
    level = [bytes.fromhex(h.removeprefix("sha256:")) for h in hashes]
    if not level:
        return "sha256:" + sha256_hex(b"")
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return "sha256:" + level[0].hex()


def pae(payload_type: str, payload: bytes) -> bytes:
    t = payload_type.encode()
    return b"DSSEv1 %d %s %d %s" % (len(t), t, len(payload), payload)


def _clause_ids(r: EvidenceRecord, by_tool: Mapping[str, list[str]]) -> list[str]:
    ids = set(by_tool.get(r.tool.split("@", 1)[0], []))
    if isinstance(r.params.get("control_id"), str):
        ids.add(r.params["control_id"])
    return sorted(ids)


def build_bundle(
    *,
    run_id: str,
    target_ref: str,
    tier: str,
    regimes: list[str],
    versions: dict[str, str],
    created_at: datetime,
    records: list[EvidenceRecord],
    decisions: list[GateDecision],
    clause_ids_by_tool: Mapping[str, list[str]],
    findings: Iterable[Finding] = (),
    status: str = "complete",
    revision: int = 0,
    previous_bundle_id: str | None = None,
    parent_bundle_id: str | None = None,
) -> AuditBundle:
    entries = [
        BundleEntry(
            record_id=r.id,
            seq=r.seq,
            hash=r.hash,
            evidence_type=r.evidence_type,
            tool=r.tool,
            clause_ids=_clause_ids(r, clause_ids_by_tool),
        )
        for r in records
    ]
    header = BundleHeader(
        bundle_id=merkle_root([r.hash for r in records]),
        run_id=run_id,
        revision=revision,
        previous_bundle_id=previous_bundle_id,
        parent_bundle_id=parent_bundle_id,
        target_ref=target_ref,
        tier=tier,
        regimes=sorted(regimes),
        versions=versions,
        created_at=created_at,
        signers=sorted({r.signer for r in records}),
    )
    return AuditBundle(
        header=header,
        entries=entries,
        decisions=list(decisions),
        findings=list(findings),
        status=status,
    )


def statement_for(bundle: AuditBundle) -> dict:
    return {
        "_type": STATEMENT_TYPE,
        "subject": [
            {
                "name": bundle.header.run_id,
                "digest": {"sha256": bundle.header.bundle_id.removeprefix("sha256:")},
            }
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": bundle.model_dump(mode="json"),
    }


def write_bundle(bundle: AuditBundle, run_dir: Path, signer: RunKey) -> Path:
    payload = canonical_json(statement_for(bundle))
    env = {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode(),
        "signatures": [
            {"keyid": signer.public_key_b64, "sig": signer.sign(pae(PAYLOAD_TYPE, payload))}
        ],
    }
    text = json.dumps(env, indent=2)
    run_dir = Path(run_dir)
    (run_dir / "bundles").mkdir(exist_ok=True)
    (run_dir / "bundles" / f"r{bundle.header.revision}.dsse.json").write_text(text)
    path = run_dir / BUNDLE_FILE
    path.write_text(text)
    return path


def read_envelope(run_dir: Path) -> tuple[dict, bytes, AuditBundle]:
    env = json.loads((Path(run_dir) / BUNDLE_FILE).read_text())  # FileNotFoundError propagates
    try:
        payload = base64.b64decode(env["payload"], validate=True)
        bundle = AuditBundle.model_validate(json.loads(payload)["predicate"])
    except (KeyError, TypeError, binascii.Error, json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"malformed bundle envelope: {type(e).__name__}") from e
    return env, payload, bundle


def read_bundle(run_dir: Path) -> AuditBundle:
    try:
        return read_envelope(run_dir)[2]
    except json.JSONDecodeError as e:
        raise ValueError(f"{BUNDLE_FILE} is not valid JSON") from e
