from maat.tools import load_builtin_tools
from maat.tools.registry import default_registry
from tests.fakes import FakeChatTarget, ctx_with
from tests.targets.test_tabular_testbed import toy


def run(tmp_path, name, target, **kw):
    load_builtin_tools()
    return default_registry.get(name)(ctx_with(tmp_path, target, agent="fairness"), **kw).result[
        "metrics"
    ]


def test_group_metrics_detect_disparity(tmp_path):
    m = run(tmp_path, "tabular_group_metrics", toy(), attribute="SEX")
    assert m["dp_diff"] > 0.1 and m["n_groups"] == 2


def test_proxy(tmp_path):
    t = toy()
    t.data["proxy"] = t.data["SEX"] * 2 + 0.01
    t.feature_columns = ["x", "proxy"]
    m = run(tmp_path, "find_proxy_features", t, attribute="SEX")
    assert m["top_proxy"] == "proxy" and m["max_proxy_auc"] > 0.95


def test_counterfactual_gap(tmp_path):

    def biased(msgs):
        return "DENY" if "Nigerian" in msgs[-1]["content"] else "APPROVE"

    m = run(tmp_path, "counterfactual_swap_test", FakeChatTarget(biased), attribute="nationality")
    assert m["max_approval_gap"] == 1.0 and m["n_templates"] == 4
