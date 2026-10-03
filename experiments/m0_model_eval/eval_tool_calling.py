"""M0: measure tool-calling reliability of candidate Ollama models (spec §6.10).
Usage: uv run python -m experiments.m0_model_eval.eval_tool_calling \
ollama:qwen3.6:27b ollama:gemma4:26b"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from maat.config import ModelRef, load_config
from maat.llm.cache import LLMCache
from maat.llm.client import LLMResponse, OllamaClient

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": n,
            "description": d,
            "parameters": {"type": "object", "properties": p, "required": list(p) if req else []},
        },
    }
    for n, d, p, req in [
        (
            "probe_prompt_injection",
            "Measure prompt-injection attack success rate.",
            {"split": {"type": "string", "enum": ["dev", "heldout"]}},
            False,
        ),
        (
            "tabular_group_metrics",
            "Group fairness metrics for a sensitive attribute.",
            {"attribute": {"type": "string"}},
            True,
        ),
        (
            "scan_pii_leakage",
            "Probe the target for personal data leakage.",
            {"limit": {"type": "integer"}},
            False,
        ),
        ("probe_ai_disclosure", "Check the system discloses it is an AI.", {}, False),
        (
            "shap_explain",
            "Global feature importance via SHAP.",
            {"sample_size": {"type": "integer"}},
            False,
        ),
    ]
]


@dataclass(frozen=True)
class Case:
    prompt: str
    expected_tool: str
    expected_args: dict = field(default_factory=dict)


CASES = [
    Case(
        "Check whether the chatbot can be hijacked by injected instructions.",
        "probe_prompt_injection",
    ),
    Case(
        "Run the held-out prompt injection probes.", "probe_prompt_injection", {"split": "heldout"}
    ),
    Case(
        "Measure injection attack success on the dev split.",
        "probe_prompt_injection",
        {"split": "dev"},
    ),
    Case(
        "Is the model fair across sex? Compute group metrics.",
        "tabular_group_metrics",
        {"attribute": "SEX"},
    ),
    Case(
        "Compute demographic parity for attribute RAC1P.",
        "tabular_group_metrics",
        {"attribute": "RAC1P"},
    ),
    Case(
        "Group fairness for age_group please.", "tabular_group_metrics", {"attribute": "age_group"}
    ),
    Case("Does the bot leak customers' personal data?", "scan_pii_leakage"),
    Case("Probe for PII leakage using 10 probes.", "scan_pii_leakage", {"limit": 10}),
    Case("Test whether the assistant tells users it is an AI.", "probe_ai_disclosure"),
    Case("EU AI Act Art. 50 disclosure check.", "probe_ai_disclosure"),
    Case("Which features drive the model's predictions?", "shap_explain"),
    Case("Explain the model globally with 200 samples.", "shap_explain", {"sample_size": 200}),
    Case(
        "Assess robustness against jailbreak-style instruction overrides.", "probe_prompt_injection"
    ),
    Case("Check privacy: can it reveal emails or phone numbers?", "scan_pii_leakage"),
    Case("Get SHAP importances.", "shap_explain"),
]


def score_response(case: Case, resp: LLMResponse) -> dict:
    tc = resp.tool_calls[0] if resp.tool_calls else None
    correct = int(tc is not None and tc.name == case.expected_tool)
    valid = int(correct and isinstance(tc.arguments, dict))
    exact = int(valid and all(tc.arguments.get(k) == v for k, v in case.expected_args.items()))
    return {"correct_tool": correct, "valid_args": valid, "exact_args": exact}


def main(models: list[str], out: Path) -> dict:
    cfg = load_config()
    report = {}
    for m in models:
        client = OllamaClient(
            ModelRef.parse(m), cfg.ollama, LLMCache(out.with_suffix(".cache.sqlite"), "live")
        )
        scores = []
        for c in CASES:
            for phrasing in (c.prompt, f"As an AI auditor: {c.prompt}"):
                resp = client.complete(
                    [
                        {"role": "system", "content": "Call exactly one tool."},
                        {"role": "user", "content": phrasing},
                    ],
                    tools=TOOLS,
                )
                scores.append(score_response(c, resp))
        report[m] = {k: sum(s[k] for s in scores) / len(scores) for k in scores[0]}
    out.write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:], Path("experiments/m0_model_eval/results.json")), indent=2))
