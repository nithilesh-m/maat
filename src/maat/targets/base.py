from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class Capability(StrEnum):
    CHAT = "chat"
    CONTEXT = "context"
    CONTEXT_OVERRIDE = "context_override"
    PREDICT = "predict"
    PREDICT_PROBA = "predict_proba"
    SNAPSHOT = "snapshot"


@dataclass(frozen=True)
class Reply:
    text: str
    contexts: tuple[str, ...] = ()


class TargetError(RuntimeError):
    """The system under audit could not be reached or returned something unusable."""


@runtime_checkable
class Target(Protocol):
    target_id: str
    version_hash: str

    def capabilities(self) -> frozenset[Capability]: ...


@runtime_checkable
class ChatCapable(Protocol):
    target_id: str
    version_hash: str

    def capabilities(self) -> frozenset[Capability]: ...

    def chat(
        self, messages: list[dict[str, str]], contexts_override: list[str] | None = None
    ) -> Reply: ...
