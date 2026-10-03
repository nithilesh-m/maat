from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_FAMILIES = [
    ("gpt-oss", "gpt-oss"),
    ("qwen", "qwen"),
    ("gemma", "gemma"),
    ("mistral", "mistral"),
    ("llama-guard", "llama"),
    ("llama", "llama"),
    ("granite", "granite"),
    ("phi", "phi"),
    ("deepseek", "deepseek"),
    ("nomic", "nomic"),
    ("claude", "anthropic"),
    ("gpt-", "openai"),
    ("gemini", "google"),
]


def model_family(name: str) -> str:
    low = name.lower()
    for prefix, fam in _FAMILIES:
        if low.startswith(prefix):
            return fam
    return low.split(":")[0]


class ModelRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: Literal["ollama", "openai_compat"]
    name: str

    @classmethod
    def parse(cls, s: str) -> ModelRef:
        provider, sep, name = s.partition(":")
        if not sep or not name:
            raise ValueError(f"model ref must look like 'ollama:<tag>', got {s!r}")
        return cls(provider=provider, name=name)

    @property
    def family(self) -> str:
        return model_family(self.name)


class ModelProfile(BaseModel):
    orchestrator: str
    specialists: str
    judges: list[str] = Field(min_length=1)
    tool_llm: str
    guard: str
    embeddings: str


class OllamaSettings(BaseModel):
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0
    seed: int = 42
    num_predict: int = 2048  # hard cap on generated tokens: small models can loop forever
    keep_alive: str = "30m"
    timeout: float = 600


class OpenAICompatSettings(BaseModel):
    base_url: str | None = None
    api_key_env: str | None = None


class Budgets(BaseModel):
    max_tool_calls_per_agent: int = 40
    max_llm_calls_per_agent: int = 60
    max_retries: int = 2


class MaatConfig(BaseModel):
    profile: str = "local"
    llm_mode: Literal["live", "record", "replay"] = "record"
    models: dict[str, ModelProfile]
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    openai_compat: OpenAICompatSettings = Field(default_factory=OpenAICompatSettings)
    budgets: Budgets = Field(default_factory=Budgets)

    def active(self) -> ModelProfile:
        if self.profile not in self.models:
            raise ConfigError(f"model profile {self.profile!r} not defined in [models]")
        return self.models[self.profile]


class ConfigError(ValueError):
    pass


def load_config(path: Path = Path("maat.toml")) -> MaatConfig:
    try:
        cfg = MaatConfig.model_validate(tomllib.loads(Path(path).read_text(encoding="utf-8")))
        cfg.active()
        if os.environ.get("OLLAMA_HOST"):
            cfg.ollama.base_url = os.environ["OLLAMA_HOST"]
        return cfg
    except (FileNotFoundError, tomllib.TOMLDecodeError, ValidationError) as e:
        raise ConfigError(f"{path}: {e}") from e
