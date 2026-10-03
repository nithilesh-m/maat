from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from maat.evidence.canonical import digest
from maat.schemas.catalog import Control
from maat.schemas.decisions import GateDecision, GateOutcome
from maat.schemas.evidence import EvidenceRecord, EvidenceType
from maat.schemas.profile import RiskTier

POLICY_DIR = Path(__file__).parent / "policies"
DATA_FILE = Path(__file__).parent / "data" / "thresholds.json"
QUERY = "data.maat.threshold.decision"


class GateEngineError(RuntimeError):
    pass


def policy_bundle_version(policy_dir: Path = POLICY_DIR, data_file: Path = DATA_FILE) -> str:
    files = sorted(Path(policy_dir).glob("*.rego")) + [Path(data_file)]
    return digest({f.name: f.read_text(encoding="utf-8") for f in files})


def _ns(t: datetime) -> int:
    return int(t.timestamp()) * 1_000_000_000 + t.microsecond * 1000


class OpaEngine:
    def __init__(
        self, policy_dir: Path = POLICY_DIR, data_file: Path = DATA_FILE, opa_bin: str = "opa"
    ) -> None:
        if shutil.which(opa_bin) is None:
            raise GateEngineError(
                "opa binary not found on PATH; install OPA >= 1.0 (brew install opa)"
            )
        self.policy_dir, self.data_file, self.opa_bin = Path(policy_dir), Path(data_file), opa_bin
        self.policy_version = policy_bundle_version(self.policy_dir, self.data_file)

    def decide(
        self,
        control: Control,
        evidence: dict[str, EvidenceRecord],
        tier: RiskTier,
        waivers: list[dict[str, Any]],
        overrides: dict[str, float],
        as_of: datetime,
    ) -> GateDecision:
        if control.predicate is None:
            raise GateEngineError(
                f"{control.id} has no predicate; it is not a quantitative control"
            )
        measured = {n: r for n, r in evidence.items() if r.evidence_type is EvidenceType.MEASURED}
        inp = {
            "tier": tier.value,
            "as_of_ns": _ns(as_of),
            "control": control.model_dump(mode="json"),
            "evidence": {n: {"id": r.id, "result": r.result} for n, r in measured.items()},
            "waivers": waivers,
            "overrides": overrides,
        }
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(inp, f)
            proc = subprocess.run(
                [
                    self.opa_bin,
                    "eval",
                    "--format",
                    "json",
                    "--data",
                    str(self.policy_dir),
                    "--data",
                    str(self.data_file),
                    "--input",
                    path,
                    QUERY,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            os.unlink(path)
        if proc.returncode != 0:
            raise GateEngineError(f"opa eval failed for {control.id}: {proc.stderr.strip()}")
        try:
            value = json.loads(proc.stdout)["result"][0]["expressions"][0]["value"]
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise GateEngineError(f"policy produced no decision for {control.id}") from e
        return GateDecision(
            clause_id=control.id,
            gate=control.gate,
            method="rego",
            policy_version=self.policy_version,
            inputs=sorted(r.id for r in evidence.values()),
            outcome=GateOutcome(value["outcome"]),
            rationale=value.get("reason", ""),
            waiver_id=value.get("waiver_id"),
        )
