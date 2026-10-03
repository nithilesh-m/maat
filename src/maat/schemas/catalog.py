from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from maat.schemas.decisions import GateOutcome
from maat.schemas.profile import RiskTier, SystemType

Dimension = Literal[
    "fairness",
    "robustness_security",
    "privacy",
    "transparency_explainability",
    "accountability_documentation",
]


class _F(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Predicate(_F):
    tool: str
    metric: str
    op: Literal["le", "ge", "eq"]
    threshold: str


class EvidenceEdge(_F):
    tool: str
    w: Literal[1, 2, 3]


class Control(_F):
    id: str = Field(pattern=r"^[A-Z]{2}-[A-Z]+-\d{2}$")
    title: str
    dimension: Dimension
    gate: Literal["DG", "TG", "VG", "RG", "OG"]
    kind: Literal["quantitative", "qualitative"]
    agent: Literal["risk", "fairness", "explainability", "compliance"]
    applies_to: list[SystemType]
    tier: Literal["R1+", "R2+", "R3"]
    criticality: Literal["low", "medium", "high"]
    non_waivable_at: list[RiskTier] = Field(default_factory=list)
    regimes: dict[str, list[str]]
    evidence_edges: list[EvidenceEdge] = Field(min_length=1)
    predicate: Predicate | None = None
    rubric: str | None = None
    manual_check: str | None = None

    @model_validator(mode="after")
    def _kind_rules(self) -> Control:
        if self.kind == "quantitative":
            if self.predicate is None:
                raise ValueError("quantitative controls need a predicate")
            if self.predicate.tool not in {e.tool for e in self.evidence_edges}:
                raise ValueError("predicate.tool must be one of the evidence_edges tools")
        if self.kind == "qualitative" and not self.rubric:
            raise ValueError("qualitative controls need a rubric")
        return self


class Catalog(_F):
    version: str
    controls: dict[str, Control]


class EvidenceLink(_F):
    record_id: str
    hash: str


class ClauseRow(_F):
    regime: str
    regime_clause: str
    control_id: str
    adequacy: int
    outcome: GateOutcome
    evidence: list[EvidenceLink] = Field(default_factory=list)
    waiver_id: str | None = None
