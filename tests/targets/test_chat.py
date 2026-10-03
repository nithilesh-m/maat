import httpx
import pytest

from maat.schemas.profile import SystemProfile
from maat.targets.base import Capability, ChatCapable, Target, TargetError
from maat.targets.chat import ChatTarget


def openai_reply(text, contexts=None):
    body = {"choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]}
    if contexts is not None:
        body["maat_contexts"] = contexts
    return body


def client_with(handler):
    return httpx.Client(base_url="http://bot/v1", transport=httpx.MockTransport(handler))


def test_chat_posts_openai_request_and_parses_reply():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["json"] = __import__("json").loads(req.content)
        return httpx.Response(200, json=openai_reply("hello", ["ctx1"]))

    t = ChatTarget(
        "bot", "http://bot/v1", "m", "mistral", returns_context=True, client=client_with(handler)
    )
    r = t.chat([{"role": "user", "content": "hi"}])
    assert r.text == "hello" and r.contexts == ("ctx1",)
    assert seen["url"] == "http://bot/v1/chat/completions"
    assert seen["json"]["temperature"] == 0 and seen["json"]["seed"] == 42
    assert isinstance(t, Target) and isinstance(t, ChatCapable)
    assert t.capabilities() == frozenset({Capability.CHAT, Capability.CONTEXT})


def test_context_override_sent_when_given():
    seen = {}

    def handler(req):
        seen["json"] = __import__("json").loads(req.content)
        return httpx.Response(200, json=openai_reply("ok"))

    t = ChatTarget("bot", "http://bot/v1", "m", "mistral", client=client_with(handler))
    t.chat([{"role": "user", "content": "q"}], contexts_override=["a", "b"])
    assert seen["json"]["maat_context_override"] == ["a", "b"]


def test_retries_then_raises_target_error():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(503)

    t = ChatTarget(
        "bot", "http://bot/v1", "m", "mistral", retries=3, backoff=0, client=client_with(handler)
    )
    with pytest.raises(TargetError, match="after 3 attempts"):
        t.chat([{"role": "user", "content": "q"}])
    assert calls["n"] == 3


def test_malformed_body_is_target_error():
    t = ChatTarget(
        "bot",
        "http://bot/v1",
        "m",
        "mistral",
        retries=1,
        backoff=0,
        client=client_with(lambda r: httpx.Response(200, json={"nope": 1})),
    )
    with pytest.raises(TargetError):
        t.chat([{"role": "user", "content": "q"}])


def test_version_hash_depends_on_config():
    a = ChatTarget("bot", "http://a/v1", "m", "mistral")
    b = ChatTarget("bot", "http://b/v1", "m", "mistral")
    assert a.version_hash != b.version_hash and a.version_hash.startswith("sha256:")


def test_from_profile_missing_env_var(monkeypatch):
    monkeypatch.delenv("MAAT_TEST_KEY", raising=False)
    prof = SystemProfile.model_validate(
        {
            "profile_version": 1,
            "name": "b",
            "system_type": "rag",
            "description": "d",
            "intended_use": "u",
            "declared_risk_tier": "limited",
            "target": {
                "adapter": "chat",
                "endpoint": "http://bot/v1",
                "model": "m",
                "model_family": "mistral",
                "auth_env": "MAAT_TEST_KEY",
            },
        }
    )
    with pytest.raises(TargetError, match="MAAT_TEST_KEY is not set"):
        ChatTarget.from_profile(prof)
