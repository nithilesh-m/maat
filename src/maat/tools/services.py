from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


def cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return 0.0 if na == 0 or nb == 0 else sum(x * y for x, y in zip(a, b, strict=False)) / (na * nb)


def require_services(ctx) -> ToolServices:
    if ctx.services is None:
        raise RuntimeError("tool services are not configured for this run (needs maat.toml)")
    return ctx.services


@dataclass
class ToolServices:
    embed: Callable[[list[str]], list[list[float]]]
    guard: Callable[[str, str], bool]
    hhem: Callable[[str, str], float]
    pii: Callable[[str], list[dict[str, Any]]]
    judge_llm: Any = None


def default_services(maat_cfg, cache) -> ToolServices:
    """Real services. `cache` is an LLMCache or a zero-arg callable returning one; it is
    resolved lazily so the run directory need not exist yet."""
    from maat.llm.client import get_client

    state: dict[str, Any] = {}

    def client(role: str):
        if role not in state:
            state[role] = get_client(role, maat_cfg, cache() if callable(cache) else cache)
        return state[role]

    def embed(texts: list[str]) -> list[list[float]]:
        return client("embeddings").embed(texts)

    def guard(prompt: str, reply: str) -> bool:
        r = client("guard").complete(
            [{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}]
        )
        return r.content.strip().lower().startswith("unsafe")

    def hhem(premise: str, hypothesis: str) -> float:
        if "hhem" not in state:
            from transformers import AutoModelForSequenceClassification

            state["hhem"] = AutoModelForSequenceClassification.from_pretrained(
                "vectara/hallucination_evaluation_model", trust_remote_code=True
            )
        return float(state["hhem"].predict([(premise, hypothesis)])[0])

    def pii(text: str) -> list[dict[str, Any]]:
        if "pii" not in state:
            from presidio_analyzer import AnalyzerEngine

            state["pii"] = AnalyzerEngine()
        return [
            {"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": r.score}
            for r in state["pii"].analyze(text=text, language="en")
        ]

    class _LazyJudge:
        def complete(self, *a, **k):
            return client("tool_llm").complete(*a, **k)

    return ToolServices(embed=embed, guard=guard, hhem=hhem, pii=pii, judge_llm=_LazyJudge())
