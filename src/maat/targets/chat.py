from __future__ import annotations

import os
import time

import httpx

from maat.evidence.canonical import digest
from maat.schemas.profile import SystemProfile
from maat.targets.base import Capability, Reply, TargetError


class ChatTarget:
    """Any OpenAI-compatible chat endpoint (optionally returning maat_contexts)."""

    def __init__(
        self,
        target_id: str,
        base_url: str,
        model: str,
        model_family: str,
        api_key: str | None = None,
        returns_context: bool = False,
        accepts_context_override: bool = False,
        timeout: float = 60.0,
        retries: int = 3,
        backoff: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.target_id = target_id
        self.model = model
        self.model_family = model_family
        self.returns_context = returns_context
        self.accepts_context_override = accepts_context_override
        self.retries = max(1, retries)
        self.backoff = backoff
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, headers=headers
        )
        self.version_hash = digest(
            {"adapter": "chat", "base_url": base_url.rstrip("/"), "model": model}
        )

    def capabilities(self) -> frozenset[Capability]:
        caps = {Capability.CHAT}
        if self.returns_context:
            caps.add(Capability.CONTEXT)
        if self.accepts_context_override:
            caps.add(Capability.CONTEXT_OVERRIDE)
        return frozenset(caps)

    def chat(
        self, messages: list[dict[str, str]], contexts_override: list[str] | None = None
    ) -> Reply:
        body: dict = {"model": self.model, "messages": messages, "temperature": 0, "seed": 42}
        if contexts_override is not None:
            body["maat_context_override"] = contexts_override
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                r = self._client.post("/chat/completions", json=body)
                r.raise_for_status()
                data = r.json()
                text = data["choices"][0]["message"]["content"] or ""
                return Reply(text=text, contexts=tuple(data.get("maat_contexts") or ()))
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
                last = e
                if attempt < self.retries - 1 and self.backoff:
                    time.sleep(self.backoff * 2**attempt)
        raise TargetError(
            f"target {self.target_id} failed after {self.retries} attempts: "
            f"{type(last).__name__}: {last}"
        )

    @classmethod
    def from_profile(cls, profile: SystemProfile, client: httpx.Client | None = None) -> ChatTarget:
        tc = profile.target
        if not tc.endpoint or not tc.model:
            raise TargetError("chat/rag targets need target.endpoint and target.model")
        api_key = None
        if tc.auth_env:
            api_key = os.environ.get(tc.auth_env)
            if api_key is None:
                raise TargetError(f"environment variable {tc.auth_env} is not set")
        return cls(
            target_id=profile.name,
            base_url=tc.endpoint,
            model=tc.model,
            model_family=tc.model_family,
            api_key=api_key,
            returns_context=tc.returns_context,
            client=client,
        )
