from experiments.m0_model_eval.eval_tool_calling import CASES, Case, score_response
from maat.llm.client import LLMResponse, ToolCall


def test_scoring():
    c = Case("p", "probe_prompt_injection", {"split": "dev"})
    good = LLMResponse(
        model="m",
        cache_key="k",
        tool_calls=[ToolCall(name="probe_prompt_injection", arguments={"split": "dev"})],
    )
    assert score_response(c, good) == {"correct_tool": 1, "valid_args": 1, "exact_args": 1}
    assert score_response(c, LLMResponse(model="m", cache_key="k"))["correct_tool"] == 0
    assert len(CASES) >= 15
