import json

from maat.agents.crosscheck import make_crosscheck
from maat.llm.client import LLMResponse
from maat.schemas.findings import Finding, FindingStatus


class Peer:
    def __init__(self, status):
        self.status = status

    def complete(self, messages, *, tools=None, schema=None):
        return LLMResponse(
            model="p",
            cache_key="k",
            content=json.dumps(
                {"status": self.status, "reason": "checked", "rerun_record_ids": []}
            ),
        )


F = [
    Finding(
        id="F-risk-000",
        agent="risk",
        clause_ids=["VG-SEC-01"],
        severity="high",
        claim="c",
        evidence_ids=["rec-0"],
    ),
    Finding(
        id="F-risk-001",
        agent="risk",
        clause_ids=["VG-SEC-01"],
        severity="low",
        claim="c",
        evidence_ids=["rec-0"],
    ),
]


def test_confirm_and_dispute():
    out = make_crosscheck(Peer("confirmed"), None, None)(F, [])
    assert out[0].status is FindingStatus.CONFIRMED and out[1].status is FindingStatus.PROPOSED
    out = make_crosscheck(Peer("disputed"), None, None)(F, [])
    assert out[0].status is FindingStatus.DISPUTED and out[0].dispute_reason == "checked"


def test_llm_error_leaves_finding_proposed():
    from maat.llm.client import LLMError

    class Down:
        def complete(self, messages, *, tools=None, schema=None):
            raise LLMError("down")

    out = make_crosscheck(Down(), None, None)(F, [])
    assert [f.status for f in out] == [FindingStatus.PROPOSED, FindingStatus.PROPOSED]


def test_rerun_is_executed_and_shown_before_final_verdict():
    class Spec:
        calls = 0

        def __call__(self, ctx, **params):
            Spec.calls += 1
            from maat.schemas.evidence import EvidenceRecord
            from tests.fakes import AS_OF

            return EvidenceRecord(
                run_id="r", agent="risk", tool="probe_prompt_injection@1.0.0",
                evidence_type="measured", target_ref="t", result={"metrics": {"asr": 0.5}},
                started_at=AS_OF, ended_at=AS_OF, id="rec-new", seq=9, prev_hash="p",
                signer="k", hash="h", sig="s",
            )  # fmt: skip

    class Registry:
        def get(self, name):
            return Spec()

    class TwoStep:
        def __init__(self):
            self.n = 0
            self.seen = []

        def complete(self, messages, *, tools=None, schema=None):
            self.n += 1
            self.seen.append(messages)
            first = self.n == 1
            body = {
                "status": "insufficient_evidence" if first else "confirmed",
                "reason": "rerun" if first else "ok",
                "rerun_record_ids": ["rec-0"] if first else [],
            }
            return LLMResponse(model="p", cache_key="k", content=json.dumps(body))

    from maat.schemas.evidence import EvidenceRecord
    from tests.fakes import AS_OF

    rec0 = EvidenceRecord(
        run_id="r", agent="risk", tool="probe_prompt_injection@1.0.0", evidence_type="measured",
        target_ref="t", result={"metrics": {"asr": 0.5}}, started_at=AS_OF, ended_at=AS_OF,
        id="rec-0", seq=0, prev_hash="p", signer="k", hash="h", sig="s",
    )  # fmt: skip
    llm = TwoStep()
    out = make_crosscheck(llm, Registry(), lambda agent: None)(F[:1], [rec0])
    assert Spec.calls == 1 and llm.n == 2
    assert "Re-run results" in llm.seen[1][-1]["content"]
    assert out[0].status is FindingStatus.CONFIRMED
