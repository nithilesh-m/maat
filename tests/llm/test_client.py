import json

import httpx
import pytest

from maat.config import ModelRef, OllamaSettings
from maat.llm.cache import CacheMiss, LLMCache
from maat.llm.client import LLMError, OllamaClient


def mk(tmp_path, mode, handler):
    return OllamaClient(
        ModelRef.parse("ollama:qwen3.6:27b"),
        OllamaSettings(),
        LLMCache(tmp_path / "c.sqlite", mode),
        http=httpx.Client(base_url="http://o", transport=httpx.MockTransport(handler)),
    )


def reply(content="", tool_calls=None):
    return httpx.Response(
        200,
        json={
            "message": {"role": "assistant", "content": content, "tool_calls": tool_calls or []},
            "prompt_eval_count": 5,
            "eval_count": 7,
        },
    )


def test_request_shape_and_tool_calls(tmp_path):
    seen = {}

    def h(req):
        seen.update(json.loads(req.content))
        return reply(tool_calls=[{"function": {"name": "t", "arguments": {"a": 1}}}])

    r = mk(tmp_path, "record", h).complete(
        [{"role": "user", "content": "x"}], tools=[{"type": "function"}], schema={"type": "object"}
    )
    assert (
        seen["options"] == {"temperature": 0.0, "seed": 42, "num_predict": 2048}
        and seen["stream"] is False
    )
    assert seen["format"] == {"type": "object"} and seen["tools"] == [{"type": "function"}]
    assert r.tool_calls[0].name == "t" and r.tool_calls[0].arguments == {"a": 1}
    assert r.usage == {"prompt_tokens": 5, "completion_tokens": 7}


def test_record_then_replay(tmp_path):
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return reply("hi")

    msgs = [{"role": "user", "content": "x"}]
    assert mk(tmp_path, "record", h).complete(msgs).content == "hi"
    r = mk(tmp_path, "replay", lambda req: pytest.fail("network in replay"))
    assert r.complete(msgs).cached and calls["n"] == 1
    with pytest.raises(CacheMiss):
        r.complete([{"role": "user", "content": "different"}])


def test_string_arguments_parsed_and_http_error(tmp_path):
    r = mk(
        tmp_path,
        "live",
        lambda req: reply(tool_calls=[{"function": {"name": "t", "arguments": '{"a": 2}'}}]),
    )
    assert r.complete([{"role": "user", "content": "x"}]).tool_calls[0].arguments == {"a": 2}
    with pytest.raises(LLMError):
        mk(tmp_path, "live", lambda req: httpx.Response(500)).complete(
            [{"role": "user", "content": "y"}]
        )


def test_generation_is_capped_with_num_predict(tmp_path):
    seen = {}

    def h(req):
        seen.update(json.loads(req.content))
        return reply("ok")

    mk(tmp_path, "live", h).complete([{"role": "user", "content": "x"}])
    assert seen["options"]["num_predict"] == OllamaSettings().num_predict > 0
    s = OllamaSettings(num_predict=64)
    client = OllamaClient(
        ModelRef.parse("ollama:m"), s, LLMCache(tmp_path / "c2.sqlite", "live"),
        http=httpx.Client(base_url="http://o", transport=httpx.MockTransport(h)),
    )  # fmt: skip
    client.complete([{"role": "user", "content": "y"}])
    assert seen["options"]["num_predict"] == 64
