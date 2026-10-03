from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class AuditOptions(BaseModel):
    """How an audit is planned and judged. Defaults are the full MAAT system; the other settings
    are the baselines (B0 static, B1 single agent, B2 LLM only) and ablations (A1-A4)."""

    model_config = ConfigDict(extra="forbid")
    planner: Literal["agents", "static", "llm_only"] = "agents"
    agent_layout: Literal["specialists", "single"] = "specialists"  # B1: one agent, all tools
    crosscheck: bool = True  # A1: False disables the peer cross-check round
    judge_mode: Literal["panel", "single", "none"] = "panel"  # A2: first judge only / no judge
    allow_same_family_judges: bool = False  # A3: ablation only
    model_profile: str | None = None  # A4: e.g. "local-small"
