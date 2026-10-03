import pytest

from maat.evidence.artifacts import ArtifactStore
from maat.evidence.ledger import Ledger
from maat.evidence.signing import RunKey
from maat.schemas.evidence import EvidenceType
from maat.targets.base import Capability
from maat.tools.contract import ToolContext, ToolResult
from maat.tools.registry import ToolRegistry, maat_tool
from tests.fakes import SEED, FakeChatTarget, fixed_clock, make_profile, robust, seq_ids


@pytest.fixture
def ctx(tmp_path):
    ledger = Ledger(tmp_path / "l.sqlite", "run-1", RunKey.from_seed(SEED), seq_ids())
    return ToolContext(
        run_id="run-1",
        agent="risk",
        target=FakeChatTarget(robust),
        ledger=ledger,
        artifacts=ArtifactStore(tmp_path / "a", "run-1"),
        profile=make_profile(),
        clock=fixed_clock(),
    )


def test_successful_tool_writes_measured_record(ctx):
    reg = ToolRegistry()

    @maat_tool("echo_metric", "1.0.0", "risk", requires=(Capability.CHAT,), registry=reg)
    def echo_metric(c: ToolContext, value: int = 1) -> ToolResult:
        """Return the given value as a metric."""
        return ToolResult(metrics={"value": value}, samples=[{"v": value}])

    rec = reg.get("echo_metric")(ctx, value=7)
    assert rec.evidence_type is EvidenceType.MEASURED
    assert rec.tool == "echo_metric@1.0.0" and rec.agent == "risk"
    assert rec.params == {"value": 7}
    assert rec.result == {"metrics": {"value": 7}, "samples": [{"v": 7}]}
    assert rec.target_ref.startswith("fake-bot@sha256:")
    assert reg.get("echo_metric").description == "Return the given value as a metric."


def test_missing_capability_writes_gap(ctx):
    reg = ToolRegistry()

    @maat_tool("needs_predict", "1.0.0", "fairness", requires=(Capability.PREDICT,), registry=reg)
    def needs_predict(c):
        raise AssertionError("must not run")

    rec = reg.get("needs_predict")(ctx)
    assert rec.evidence_type is EvidenceType.GAP
    assert "lacks capabilities" in rec.result["error"] and "predict" in rec.result["error"]


def test_exception_writes_gap_not_raise(ctx):
    reg = ToolRegistry()

    @maat_tool("explodes", "1.0.0", "risk", registry=reg)
    def explodes(c):
        raise ValueError("boom")

    rec = reg.get("explodes")(ctx)
    assert rec.evidence_type is EvidenceType.GAP
    assert rec.result["error"] == "ValueError: boom"


def test_duplicate_tool_name_rejected():
    reg = ToolRegistry()
    maat_tool("t", "1.0.0", "risk", registry=reg)(lambda c: ToolResult(metrics={}))
    with pytest.raises(ValueError, match="duplicate"):
        maat_tool("t", "2.0.0", "risk", registry=reg)(lambda c: ToolResult(metrics={}))


def test_registry_versions_sorted():
    reg = ToolRegistry()
    maat_tool("b", "1.0.0", "risk", registry=reg)(lambda c: ToolResult(metrics={}))
    maat_tool("a", "2.0.0", "risk", registry=reg)(lambda c: ToolResult(metrics={}))
    assert reg.names() == ["a", "b"]
    assert reg.versions() == {"a": "2.0.0", "b": "1.0.0"}
