from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MitigationSpec(BaseModel):
    id: str
    control_ids: list[str]
    description: str
    applies_to_adapter: Literal["testbed", "tabular"]
    params: dict[str, Any] = Field(default_factory=dict)


class MitigationPlan(BaseModel):
    control_id: str
    mitigation_id: str
    rationale: str
    severity_score: float
