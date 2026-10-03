from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from maat.config import MaatConfig, ModelRef, OllamaSettings, OpenAICompatSettings
from maat.evidence.canonical import digest
from maat.llm.cache import CacheMiss, LLMCache


class LLMError(RuntimeError):
    pass


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model: str
    cache_key: str
    usage: dict[str, int] = Field(default_factory=dict)
    cached: bool = False


class LLMClient(Protocol):
    ref: ModelRef

    def complete(
        self, messages: list[dict], *, tools: list[dict] | None = None, schema: dict | None = None
    ) -> LLMResponse: ...


def _args(a: Any) -> dict:
    if isinstance(a, dict):
        return a
    try:
        v = json.loads(a or "{}")
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        return {}


class _Cached:
    ref: ModelRef
    cache: LLMCache

    def _through_cache(self, key: str, body: dict, call) -> tuple[dict, bool]:
        hit = self.cache.get(key) if self.cache.mode != "live" else None
        if hit is not None:
            return hit, True
        if self.cache.mode == "replay":
            raise CacheMiss(f"no cached response for {self.ref.name} request {key}")
        try:
            data = call()
        except (httpx.HTTPError, ValueError) as e:
            raise LLMError(
                f"{self.ref.provider}:{self.ref.name} failed: {type(e).__name__}: {e}"
            ) from e
        self.cache.put(key, body, data)
        return data, False


class OllamaClient(_Cached):
    def __init__(
        self,
        ref: ModelRef,
        settings: OllamaSettings,
        cache: LLMCache,
        http: httpx.Client | None = None,
    ) -> None:
        self.ref, self.settings, self.cache = ref, settings, cache
        self._http = http or httpx.Client(base_url=settings.base_url, timeout=settings.timeout)

    def _post(self, path: str, body: dict) -> dict:
        r = self._http.post(path, json={**body, "keep_alive": self.settings.keep_alive})
        r.raise_for_status()
        return r.json()

    def complete(self, messages, *, tools=None, schema=None) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.ref.name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.settings.temperature,
                "seed": self.settings.seed,
                "num_predict": self.settings.num_predict,
            },
        }
        if tools:
            body["tools"] = tools
        if schema:
            body["format"] = schema
        key = digest({"provider": "ollama", **body})
        data, cached = self._through_cache(key, body, lambda: self._post("/api/chat", body))
        try:
            msg = data["message"]
        except (KeyError, TypeError) as e:
            raise LLMError(f"malformed Ollama response from {self.ref.name}") from e
        calls = [
            ToolCall(name=tc["function"]["name"], arguments=_args(tc["function"].get("arguments")))
            for tc in msg.get("tool_calls") or []
        ]
        return LLMResponse(
            content=msg.get("content") or "",
            tool_calls=calls,
            model=self.ref.name,
            cache_key=key,
            cached=cached,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        body = {"model": self.ref.name, "input": texts}
        key = digest({"provider": "ollama-embed", **body})
        data, _ = self._through_cache(key, body, lambda: self._post("/api/embed", body))
        return data["embeddings"]


class OpenAICompatClient(_Cached):
    """Optional hybrid plugin. Off by default; never required."""

    def __init__(self, ref: ModelRef, settings: OpenAICompatSettings, cache: LLMCache) -> None:
        if not settings.base_url or not settings.api_key_env:
            raise LLMError("openai_compat needs base_url and api_key_env in maat.toml")
        key = os.environ.get(settings.api_key_env)
        if key is None:
            raise LLMError(f"environment variable {settings.api_key_env} is not set")
        self.ref, self.cache = ref, cache
        self._http = httpx.Client(
            base_url=settings.base_url, timeout=600, headers={"Authorization": f"Bearer {key}"}
        )

    def complete(self, messages, *, tools=None, schema=None) -> LLMResponse:
        body: dict[str, Any] = {"model": self.ref.name, "messages": messages}
        if tools:
            body["tools"] = tools
        if schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "out", "schema": schema},
            }
        key = digest({"provider": "openai_compat", **body})

        def call():
            r = self._http.post("/chat/completions", json=body)
            r.raise_for_status()
            return r.json()

        data, cached = self._through_cache(key, body, call)
        msg = data["choices"][0]["message"]
        calls = [
            ToolCall(name=t["function"]["name"], arguments=_args(t["function"]["arguments"]))
            for t in msg.get("tool_calls") or []
        ]
        u = data.get("usage") or {}
        return LLMResponse(
            content=msg.get("content") or "",
            tool_calls=calls,
            model=self.ref.name,
            cache_key=key,
            cached=cached,
            usage={
                "prompt_tokens": u.get("prompt_tokens", 0),
                "completion_tokens": u.get("completion_tokens", 0),
            },
        )


def _make(ref_s: str, cfg: MaatConfig, cache: LLMCache) -> LLMClient:
    ref = ModelRef.parse(ref_s)
    if ref.provider == "ollama":
        return OllamaClient(ref, cfg.ollama, cache)
    return OpenAICompatClient(ref, cfg.openai_compat, cache)


def get_client(role: str, cfg: MaatConfig, cache: LLMCache) -> LLMClient:
    return _make(getattr(cfg.active(), role), cfg, cache)


def get_judges(cfg: MaatConfig, cache: LLMCache) -> list[LLMClient]:
    return [_make(j, cfg, cache) for j in cfg.active().judges]
