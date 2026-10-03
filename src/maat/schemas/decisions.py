from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GateOutcome(StrEnum):
    PASS = "pass"
    WAIVE = "waive"
    BLOCK = "block"
    FAIL = "fail"
    ABSTAIN = "abstain"
    NOT_APPLICABLE = "not_applicable"


class JudgeVote(BaseModel):
    model_config = ConfigDict(frozen=True)
    model: str
    label: Literal["S", "P", "N", "NA", "invalid"]
    confidence: float = 0.0
    cited: list[str] = Field(default_factory=list)


class GateDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    clause_id: str
    gate: str
    method: Literal["rego", "judge_panel", "human", "none"]
    policy_version: str
    inputs: list[str] = Field(default_factory=list)
    outcome: GateOutcome
    rationale: str = ""
    partial: bool = False
    judges: list[JudgeVote] = Field(default_factory=list)
    agreement: float | None = None
    waiver_id: str | None = None
