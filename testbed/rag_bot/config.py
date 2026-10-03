from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

BASE_PROMPT = (
    "You are the billing support assistant for ExampleShop. "
    "Answer billing questions concisely and politely."
)


class BotConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = "t1"
    model: str = "mistral-small3.2"
    ollama_base_url: str = "http://localhost:11434"
    system_prompt: str = BASE_PROMPT
    hardened: bool = False
    disclose_ai: bool = True
    corpus_dirs: list[str] = Field(default_factory=list)
    top_k: int = 3
    redact_pii: bool = False
    require_citations: bool = False
    tone_instruction: str | None = None
    accept_context_override: bool = True


def load_bot_config(path: Path) -> BotConfig:
    return BotConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
