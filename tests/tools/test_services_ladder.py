import time

import pytest

from maat.schemas.evidence import EvidenceType
from maat.tools.contract import ToolResult
from maat.tools.registry import ToolRegistry, maat_tool
from maat.tools.services import cosine
from tests.tools.test_contract import ctx  # noqa: F401  (fixture reuse)


def test_cosine():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0) and cosine([1, 0], [0, 1]) == pytest.approx(
        0.0
    )
    assert cosine([0, 0], [1, 0]) == 0.0


def test_timeout_becomes_gap(ctx):  # noqa: F811
    reg = ToolRegistry()

    @maat_tool("slow", "1.0.0", "risk", timeout=0.2, registry=reg)
    def slow(c):
        time.sleep(2)
        return ToolResult(metrics={})

    rec = reg.get("slow")(ctx)
    assert rec.evidence_type is EvidenceType.GAP and "TimeoutError" in rec.result["error"]


def test_metrics_declared():
    reg = ToolRegistry()
    maat_tool("m", "1.0.0", "risk", metrics=("asr",), registry=reg)(
        lambda c: ToolResult(metrics={"asr": 0})
    )
    assert reg.get("m").extra["metrics"] == ("asr",)
