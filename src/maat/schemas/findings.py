from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    agent: str
    clause_ids: list[str] = Field(min_length=1)
    severity: Severity
    claim: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    status: FindingStatus = FindingStatus.PROPOSED
    dispute_reason: str | None = None
