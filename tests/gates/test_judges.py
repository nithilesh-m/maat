import json

import pytest

from maat.catalog.loader import load_catalog
from maat.gates.judges import make_judge
from maat.llm.client import LLMResponse
from maat.schemas.decisions import GateOutcome
from maat.schemas.evidence import EvidenceRecord
from tests.fakes import AS_OF

C = load_catalog().controls["RG-OVS-01"]
R = EvidenceRecord(
    run_id="r",
    agent="compliance",
    tool="check_logging_and_oversight@1.0.0",
    evidence_type="measured",
    target_ref="t",
    result={"metrics": {"oversight_evidence": 1}, "samples": []},
    started_at=AS_OF,
    ended_at=AS_OF,
    id="rec-7",
    seq=7,
    prev_hash="p",
    signer="k",
    hash="h",
    sig="s",
)


class J:
    def __init__(self, label, cite=("rec-7",)):
        self.label, self.cite, self.ref = label, list(cite), type("R", (), {"name": label})

    def complete(self, messages, *, tools=None, schema=None):
        return LLMResponse(
            model="j",
            cache_key="k",
            content=json.dumps(
                {
                    "label": self.label,
                    "cited_record_ids": self.cite,
                    "cited_spans": [],
                    "confidence": 0.8,
                    "rationale": "r",
                }
            ),
        )


def decide(*judges):
    return make_judge(list(judges), "p")(C, {"check_logging_and_oversight": R})


def test_majority_pass_and_partial():
    d = decide(J("S"), J("S"), J("N"))
    assert (
        d.outcome is GateOutcome.PASS
        and d.method == "judge_panel"
        and abs(d.agreement - 2 / 3) < 1e-9
    )
    assert decide(J("P"), J("P"), J("S")).partial


def test_invalid_citations_and_no_majority_abstain():
    assert decide(J("S", cite=["rec-999"]), J("S", cite=[]), J("S")).outcome is GateOutcome.ABSTAIN
    assert decide(J("S"), J("N"), J("P")).outcome is GateOutcome.ABSTAIN


def test_fail_mapping():
    assert decide(J("N"), J("N"), J("S")).outcome is GateOutcome.FAIL


def test_judge_cache_miss_propagates_so_replay_cannot_hide_it():
    from maat.llm.cache import CacheMiss

    class Missing:
        ref = type("R", (), {"name": "m"})

        def complete(self, messages, *, tools=None, schema=None):
            raise CacheMiss("not recorded")

    with pytest.raises(CacheMiss):
        decide(Missing(), Missing(), Missing())
