from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from maat.schemas.catalog import Control
from maat.schemas.profile import RiskTier, SystemType


class ERS(BaseModel):
    purpose: str
    stakeholders: list[str] = Field(default_factory=list)
    prohibited_uses: list[str] = Field(default_factory=list)
    sensitive_groups: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)


def load_ers(path: Path) -> ERS:
    return ERS.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


class ClassifyOut(BaseModel):
    system_type: SystemType
    suggested_tier: RiskTier
    rationale: str


class AuditPlan(BaseModel):
    assignments: dict[str, list[str]]
    not_applicable: dict[str, str] = Field(default_factory=dict)


def plan_from_controls(controls: list[Control]) -> AuditPlan:
    out: dict[str, list[str]] = {}
    for c in controls:
        out.setdefault(c.agent, []).append(c.id)
    return AuditPlan(assignments=out)
