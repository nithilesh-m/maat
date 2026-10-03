from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from maat.agents.tooling import summarize_record
from maat.llm.client import LLMError
from maat.llm.untrusted import UNTRUSTED_NOTICE, NullScreen
from maat.schemas.findings import Finding, FindingStatus, Severity

PEERS = {
    "risk": "compliance",
    "compliance": "risk",
    "fairness": "explainability",
    "explainability": "fairness",
}
REVIEWED = {Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL}


class CrossCheckOut(BaseModel):
    status: Literal["confirmed", "disputed", "insufficient_evidence"]
    reason: str
    rerun_record_ids: list[str] = Field(default_factory=list, max_length=2)


def make_crosscheck(llm, registry, make_ctx, max_reruns: int = 2):
    screen = NullScreen()

    def run(findings: list[Finding], records) -> list[Finding]:
        by_id = {r.id: r for r in records}
        out = []
        for f in findings:
            if f.severity not in REVIEWED:
                out.append(f)
                continue
            cited = "\n".join(
                summarize_record(by_id[i], screen) for i in f.evidence_ids if i in by_id
            )
            msgs = [
                {
                    "role": "system",
                    "content": f"You are the {PEERS.get(f.agent, 'peer')} agent reviewing a "
                    "peer's finding. Check ONLY whether the cited evidence supports the claim. "
                    + UNTRUSTED_NOTICE,
                },
                {
                    "role": "user",
                    "content": f"Finding ({f.severity.value}) on {f.clause_ids}: {f.claim}\n"
                    f"Cited evidence:\n{cited or '(none resolvable)'}",
                },
            ]
            try:
                v = CrossCheckOut.model_validate(
                    json.loads(llm.complete(msgs, schema=CrossCheckOut.model_json_schema()).content)
                )
                if v.rerun_record_ids and registry is not None and make_ctx is not None:
                    reruns = []
                    for rid in v.rerun_record_ids[:max_reruns]:
                        r = by_id.get(rid)
                        spec = registry.get(r.tool.split("@", 1)[0]) if r else None
                        if spec:
                            reruns.append(
                                summarize_record(
                                    spec(make_ctx(PEERS.get(f.agent, "risk")), **r.params), screen
                                )
                            )
                    msgs += [
                        {"role": "assistant", "content": v.model_dump_json()},
                        {
                            "role": "user",
                            "content": "Re-run results:\n"
                            + "\n".join(reruns)
                            + "\nGive your final verdict.",
                        },
                    ]
                    v = CrossCheckOut.model_validate(
                        json.loads(
                            llm.complete(msgs, schema=CrossCheckOut.model_json_schema()).content
                        )
                    )
            except (LLMError, ValidationError, json.JSONDecodeError):
                out.append(f)
                continue
            status = FindingStatus(v.status)
            out.append(
                f.model_copy(
                    update={
                        "status": status,
                        "dispute_reason": v.reason
                        if status is not FindingStatus.CONFIRMED
                        else None,
                    }
                )
            )
        return out

    return run
