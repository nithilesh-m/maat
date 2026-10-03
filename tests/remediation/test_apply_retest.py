import pytest

from maat.remediation.apply import SandboxError, apply_mitigation
from maat.remediation.catalog import MITIGATIONS
from maat.targets.testbed import TestbedTarget
from testbed.rag_bot.config import BotConfig
from tests.fakes import make_profile
from tests.targets.test_tabular_testbed import toy

HARDEN = next(m for m in MITIGATIONS if m.id == "M-HARDEN")
THRESH = next(m for m in MITIGATIONS if m.id == "M-THRESH")


def test_sandbox_guard():
    t = TestbedTarget(BotConfig(), upstream=lambda m, c: "ok")
    with pytest.raises(SandboxError):
        apply_mitigation(t, make_profile(), HARDEN)
    s = apply_mitigation(t, make_profile(sandbox_allowed=True), HARDEN)
    assert s.cfg.hardened and not t.cfg.hardened


def test_threshold_optimizer_reduces_dp_gap():
    from fairlearn.metrics import demographic_parity_difference as dpd

    t = toy()
    t.train = t.data
    s = apply_mitigation(
        t, make_profile(sandbox_allowed=True, sensitive_attributes=["SEX"]), THRESH
    )
    before = dpd(t.y, t.predict(t.X), sensitive_features=t.data.SEX)
    after = dpd(t.y, s.predict(s.X), sensitive_features=t.data.SEX)
    assert after < before


def test_drop_feature_and_reweigh_retrain_snapshots():
    from maat.schemas.remediation import MitigationSpec

    t = toy()
    t.train = t.data
    prof = make_profile(sandbox_allowed=True, sensitive_attributes=["SEX"])
    drop = MitigationSpec(
        id="M-DROPPROXY",
        control_ids=["VG-FAIR-03"],
        description="d",
        applies_to_adapter="tabular",
        params={"method": "drop_feature", "feature": "SEX"},
    )
    s = apply_mitigation(t, prof, drop)
    assert "SEX" not in s.feature_columns and s.version_hash != t.version_hash
    rew = next(m for m in MITIGATIONS if m.id == "M-REWEIGH")
    r = apply_mitigation(t, prof, rew)
    assert r.predict(r.X).shape == (200,)


def test_sandbox_guard_requires_snapshot_capability():
    from maat.targets.base import Capability
    from tests.fakes import FakeChatTarget

    target = FakeChatTarget(lambda m: "x", caps=frozenset({Capability.CHAT}))
    with pytest.raises(SandboxError):
        apply_mitigation(target, make_profile(sandbox_allowed=True), HARDEN)


def test_utility_tools_report_metrics(tmp_path):
    from maat.targets.base import Capability
    from maat.tools import load_builtin_tools
    from maat.tools.registry import default_registry
    from tests.fakes import FakeChatTarget, ctx_with

    load_builtin_tools()
    qa = tmp_path / "qa.yaml"
    qa.write_text('items:\n  - {q: "When due?", a: "the 5th"}\n  - {q: "Refund?", a: "14 days"}\n')
    t = FakeChatTarget(lambda m: "It is due on the 5th.", caps=frozenset({Capability.CHAT}))
    prof = make_profile(artifacts={"qa_set": str(qa)})
    rec = default_registry.get("task_utility")(ctx_with(tmp_path / "a", t, None, prof))
    assert rec.result["metrics"]["qa_accuracy"] == 0.5
    rec = default_registry.get("task_utility")(
        ctx_with(tmp_path / "b", t, None, prof), which="baseline"
    )
    assert rec.params == {"which": "baseline"}
    perf = default_registry.get("tabular_performance")(ctx_with(tmp_path / "c", toy()))
    assert 0.5 < perf.result["metrics"]["accuracy"] <= 1 and perf.result["metrics"]["auroc"] > 0.5
