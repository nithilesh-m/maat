from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EvidenceType(StrEnum):
    MEASURED = "measured"
    LLM_JUDGMENT = "llm_judgment"
    MANUAL_NEEDED = "manual_needed"
    GAP = "gap"
    HUMAN_DECISION = "human_decision"
    WAIVER = "waiver"


class ArtifactRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    uri: str
    sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    sensitive: bool = False


class EvidenceDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    run_id: str
    agent: str
    tool: str
    evidence_type: EvidenceType
    target_ref: str
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    llm_calls: list[str] = Field(default_factory=list)
    started_at: AwareDatetime
    ended_at: AwareDatetime


class EvidenceRecord(EvidenceDraft):
    id: str
    seq: int
    prev_hash: str
    signer: str
    hash: str
    sig: str

    def hash_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"hash", "sig", "signer"})
