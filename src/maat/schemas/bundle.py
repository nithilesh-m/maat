from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from maat.schemas.decisions import GateDecision
from maat.schemas.evidence import EvidenceType
from maat.schemas.findings import Finding
from maat.schemas.profile import RiskTier


class _F(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BundleHeader(_F):
    bundle_id: str
    run_id: str
    revision: int = 0
    previous_bundle_id: str | None = None
    parent_bundle_id: str | None = None
    target_ref: str
    tier: RiskTier
    regimes: list[str]
    versions: dict[str, str]
    created_at: AwareDatetime
    signers: list[str]


class BundleEntry(_F):
    record_id: str
    seq: int
    hash: str
    evidence_type: EvidenceType
    tool: str
    clause_ids: list[str]


class AuditBundle(_F):
    header: BundleHeader
    entries: list[BundleEntry]
    decisions: list[GateDecision]
    findings: list[Finding] = Field(default_factory=list)
    status: Literal["complete", "incomplete", "pending_review"] = "complete"
