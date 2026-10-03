from __future__ import annotations

import json
import random
from collections import Counter

from pydantic import BaseModel, Field, ValidationError

from maat.llm.client import LLMClient, LLMError
from maat.llm.untrusted import UNTRUSTED_NOTICE, InjectionScreen, NullScreen, prepare_untrusted
from maat.schemas.catalog import Control
from maat.schemas.decisions import GateDecision, GateOutcome, JudgeVote
from maat.schemas.evidence import EvidenceRecord

OUT = {
    "S": GateOutcome.PASS,
    "P": GateOutcome.PASS,
    "N": GateOutcome.FAIL,
    "NA": GateOutcome.NOT_APPLICABLE,
}


class JudgeVerdict(BaseModel):
    label: str = Field(pattern="^(S|P|N|NA)$")
    cited_record_ids: list[str]
    cited_spans: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    rationale: str


def evidence_pack(control: Control, records: list[EvidenceRecord]) -> list[dict]:
    return [
        {
            "record_id": r.id,
            "tool": r.tool,
            "evidence_type": r.evidence_type.value,
            "metrics": r.result.get("metrics"),
            "error": r.result.get("error"),
            "checklist": r.result.get("checklist"),
            "samples": json.dumps(r.result.get("samples") or [])[:1500],
        }
        for r in records
    ]


def make_judge(
    judges: list[LLMClient],
    policy_version: str,
    seed: int = 42,
    screen: InjectionScreen | None = None,
):
    screen = screen or NullScreen()

    def judge(control: Control, evidence: dict[str, EvidenceRecord]) -> GateDecision:
        records = sorted(evidence.values(), key=lambda r: r.seq)
        pack, ids = evidence_pack(control, records), {r.id for r in records}
        votes: list[JudgeVote] = []
        for i, j in enumerate(judges):
            items = pack[:]
            random.Random(seed + i).shuffle(items)
            wrapped = prepare_untrusted(json.dumps(items), "evidence", screen, threshold=1.1)
            msgs = [
                {
                    "role": "system",
                    "content": "You are an independent compliance judge. Answer the "
                    "rubric using ONLY the evidence. Labels: S=satisfied, P=partially, "
                    "N=not satisfied, NA=not applicable. Cite record_ids you relied on. "
                    + UNTRUSTED_NOTICE,
                },
                {
                    "role": "user",
                    "content": f"Control {control.id}: {control.title}\nRubric: {control.rubric}\n"
                    f"Evidence:\n{wrapped}",
                },
            ]
            label, conf, cited = "invalid", 0.0, []
            try:
                v = JudgeVerdict.model_validate(
                    json.loads(j.complete(msgs, schema=JudgeVerdict.model_json_schema()).content)
                )
                if v.cited_record_ids and set(v.cited_record_ids) <= ids:
                    label, conf, cited = v.label, v.confidence, v.cited_record_ids
            except (LLMError, ValidationError, json.JSONDecodeError):
                pass
            votes.append(
                JudgeVote(
                    model=getattr(j.ref, "name", "judge"), label=label, confidence=conf, cited=cited
                )
            )
        valid = [v.label for v in votes if v.label != "invalid"]
        invalid = len(votes) - len(valid)
        top = Counter(valid).most_common(2)
        base = dict(
            clause_id=control.id,
            gate=control.gate,
            method="judge_panel",
            policy_version=policy_version,
            inputs=sorted(ids),
            judges=votes,
        )
        if (
            invalid > 1
            or not top
            or (len(top) > 1 and top[0][1] == top[1][1])
            or top[0][1] * 2 <= len(votes)
        ):
            return GateDecision(
                **base,
                outcome=GateOutcome.ABSTAIN,
                rationale="judges did not agree; human review needed",
                agreement=(top[0][1] / len(votes)) if top else 0.0,
            )
        label = top[0][0]
        return GateDecision(
            **base,
            outcome=OUT[label],
            partial=label == "P",
            rationale=f"panel majority {label} ({top[0][1]}/{len(votes)})",
            agreement=top[0][1] / len(votes),
        )

    return judge
