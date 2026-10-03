import pytest

import maat.tools.risk.jailbreak as jb
from maat.schemas.evidence import EvidenceType
from maat.targets.base import Capability, Reply
from maat.tools import load_builtin_tools
from maat.tools.registry import default_registry
from tests.fakes import FakeChatTarget, ctx_with, fake_services, make_profile


class CtxTarget(FakeChatTarget):
    def chat(self, messages, contexts_override=None):
        return Reply(text=self._responder(messages), contexts=("Bills are due on the 5th.",))


def tool(n):
    load_builtin_tools()
    return default_registry.get(n)


def test_jailbreak_counts_unsafe(tmp_path, monkeypatch):
    monkeypatch.setattr(jb, "load_behaviors", lambda split: ["do a bad thing", "another"])
    rec = tool("probe_jailbreak")(
        ctx_with(tmp_path, FakeChatTarget(lambda m: "sure"), fake_services(unsafe=True)), limit=2
    )
    m = rec.result["metrics"]
    assert m["n"] == 8 and m["asr"] == 1.0 and rec.artifacts[0].sensitive


def test_pii_leak_rate(tmp_path):
    hits = [{"entity_type": "PHONE_NUMBER", "start": 0, "end": 5, "score": 0.9}]
    rec = tool("scan_pii_leakage")(
        ctx_with(tmp_path, FakeChatTarget(lambda m: "call 555"), fake_services(pii_hits=hits))
    )
    assert rec.result["metrics"]["leak_rate"] == 1.0 and rec.result["metrics"]["n"] == 8


def test_hallucination_needs_qa_set(tmp_path):
    t = CtxTarget(lambda m: "due 5th", caps=frozenset({Capability.CHAT, Capability.CONTEXT}))
    rec = tool("test_hallucination")(ctx_with(tmp_path, t))
    assert rec.evidence_type is EvidenceType.GAP and "qa_set" in rec.result["error"]
    qa = tmp_path / "qa.yaml"
    qa.write_text('items:\n  - {q: "When are bills due?", a: the 5th}\n')
    prof = make_profile(artifacts={"qa_set": str(qa)})
    rec = tool("test_hallucination")(
        ctx_with(tmp_path / "b", t, fake_services(hhem_score=0.2), prof)
    )
    assert rec.result["metrics"]["faithfulness_rate"] == 0.0


@pytest.mark.parametrize("name", ["probe_jailbreak", "scan_pii_leakage"])
def test_service_tools_gap_cleanly_without_services(tmp_path, name):
    ctx = ctx_with(tmp_path, FakeChatTarget(lambda m: "x"))
    ctx.services = None
    rec = tool(name)(ctx)
    assert rec.evidence_type is EvidenceType.GAP and "services" in rec.result["error"]
