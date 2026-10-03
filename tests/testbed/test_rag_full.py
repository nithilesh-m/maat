from fastapi.testclient import TestClient

from testbed.rag_bot.app import create_app
from testbed.rag_bot.config import BotConfig
from testbed.rag_bot.retrieval import Retriever


def echo_system(messages, cfg):
    return messages[0]["content"][-300:]


def test_retrieval_and_contexts():
    r = Retriever(["testbed/rag_bot/corpus"])
    assert "5th" in " ".join(r.top("When is my bill due?", 3))
    c = TestClient(
        create_app(BotConfig(corpus_dirs=["testbed/rag_bot/corpus"]), upstream=echo_system),
        base_url="http://t/v1",
    )
    body = c.post(
        "/chat/completions",
        json={"messages": [{"role": "user", "content": "When is my bill due?"}]},
    ).json()
    assert body["maat_contexts"] and "[1]" in body["choices"][0]["message"]["content"]


def test_override_and_redaction():
    cfg = BotConfig(redact_pii=True)
    c = TestClient(
        create_app(cfg, upstream=lambda m, c: "mail anna@example.com or +49 151 2345678"),
        base_url="http://t/v1",
    )
    body = c.post(
        "/chat/completions",
        json={"messages": [{"role": "user", "content": "x"}], "maat_context_override": ["P1"]},
    ).json()
    assert body["maat_contexts"] == ["P1"] and "@" not in body["choices"][0]["message"]["content"]


def test_seeded_corpus_is_deterministic(tmp_path):
    from testbed.rag_bot.build_seeded import build

    build(tmp_path / "a")
    build(tmp_path / "b")
    assert (tmp_path / "a" / "customer_records.md").read_text() == (
        tmp_path / "b" / "customer_records.md"
    ).read_text()
