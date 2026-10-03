from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class SystemType(StrEnum):
    LLM_APP = "llm_app"
    RAG = "rag"
    AGENT = "agent"
    TABULAR_ML = "tabular_ml"


class RiskTier(StrEnum):
    MINIMAL = "minimal"
    LIMITED = "limited"
    HIGH = "high"


TIER_LEVEL: dict[RiskTier, int] = {RiskTier.MINIMAL: 1, RiskTier.LIMITED: 2, RiskTier.HIGH: 3}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TargetConfig(_Strict):
    adapter: Literal["chat", "rag", "tabular", "agent", "testbed"]
    endpoint: str | None = None
    model: str | None = None
    auth_env: str | None = None
    returns_context: bool = False
    model_family: str
    config: str | None = None  # testbed variant config path (adapter=testbed)

    @field_validator("auth_env")
    @classmethod
    def _env_name_only(cls, v: str | None) -> str | None:
        if v is not None and not _ENV_NAME.fullmatch(v):
            raise ValueError(
                "auth_env must be an environment variable NAME such as TARGET_API_KEY, "
                "never the secret itself"
            )
        return v


class TabularConfig(_Strict):
    dataset: str
    label_column: str
    positive_label: int | str = 1
    model_file: str
    train_dataset: str | None = None
    reference_dataset: str | None = None
    feature_columns: list[str] | None = None


class ArtifactPaths(_Strict):
    docs: list[str] = Field(default_factory=list)
    corpus: str | None = None
    logs: str | None = None
    qa_set: str | None = None


class SystemProfile(_Strict):
    profile_version: Literal[1]
    name: str = Field(min_length=1)
    system_type: SystemType
    description: str
    intended_use: str
    users: list[str] = Field(default_factory=list)
    deployment_region: list[str] = Field(default_factory=list)
    declared_risk_tier: RiskTier
    annex_iii_category: str | None = None
    target: TargetConfig
    tabular: TabularConfig | None = None
    artifacts: ArtifactPaths = Field(default_factory=ArtifactPaths)
    sensitive_attributes: list[str] = Field(default_factory=list)
    data_egress: Literal["local_only", "allowed"] = "local_only"
    sandbox_allowed: bool = False
    ers: str | None = None
