from maat.targets.base import Capability, Reply
from maat.tools import load_builtin_tools
from maat.tools.registry import default_registry
from tests.fakes import FakeChatTarget, ctx_with, fake_services, make_profile
from tests.targets.test_tabular_testbed import toy

CAPS = frozenset({Capability.CHAT, Capability.CONTEXT, Capability.CONTEXT_OVERRIDE})


class RagFake(FakeChatTarget):
    """Answer = first context; cites passage 1."""

    def chat(self, messages, contexts_override=None):
        ctxs = (
            contexts_override if contexts_override is not None else ["A due 5th", "B refunds 14d"]
        )
        last = messages[-1]["content"]
        if "Which passage" in last:
            return Reply(text="1", contexts=tuple(ctxs))
        return Reply(text=ctxs[0] if ctxs else "unknown", contexts=tuple(ctxs))


def EMB(ts):  # noqa: N802
    return [[1.0, 0.0] if t.startswith("A") else [0.0, 1.0] for t in ts]


def run(tmp_path, name, target, prof=None, **kw):
    load_builtin_tools()
    return default_registry.get(name)(
        ctx_with(tmp_path, target, fake_services(embed=EMB), prof, agent="explainability"), **kw
    ).result["metrics"]


def test_shap(tmp_path):
    m = run(
        tmp_path, "shap_explain", toy(), make_profile(sensitive_attributes=["SEX"]), sample_size=50
    )
    assert m["n_features"] == 2 and m["sensitive_in_top"] == 1


def test_faithfulness(tmp_path):
    qa = tmp_path / "qa.yaml"
    qa.write_text('items:\n  - {q: "When due?", a: 5th}\n')
    m = run(
        tmp_path / "r",
        "self_explanation_faithfulness",
        RagFake(None, caps=CAPS),
        make_profile(artifacts={"qa_set": str(qa)}),
    )
    assert m["faithfulness_rate"] == 1.0


def test_consistency(tmp_path):
    m = run(tmp_path, "output_consistency", FakeChatTarget(lambda msgs: "A same answer"))
    assert m["consistency_rate"] == 1.0 and m["n"] == 6
