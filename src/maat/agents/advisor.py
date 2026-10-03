from __future__ import annotations

import json

from pydantic import BaseModel

from maat.llm.client import LLMError
from maat.remediation.catalog import mitigations_for
from maat.schemas.bundle import AuditBundle
from maat.schemas.catalog import Catalog, Control
from maat.schemas.decisions import GateDecision
from maat.schemas.remediation import MitigationPlan

CRIT = {"low": 1, "medium": 2, "high": 3}
TIER = {"minimal": 1, "limited": 2, "high": 3}
OUTW = {"block": 3, "fail": 3, "waive": 2, "abstain": 1}


def severity_score(control: Control, decision: GateDecision, tier: str) -> float:
    return float(CRIT[control.criticality] * TIER[str(tier)] * OUTW.get(decision.outcome.value, 0))


def rank_findings(bundle: AuditBundle, catalog: Catalog) -> list[tuple[str, float]]:
    tier = bundle.header.tier.value
    scored = [
        (d.clause_id, severity_score(catalog.controls[d.clause_id], d, tier))
        for d in bundle.decisions
        if d.clause_id in catalog.controls
    ]
    return sorted([s for s in scored if s[1] > 0], key=lambda s: (-s[1], s[0]))


class _Choice(BaseModel):
    mitigation_id: str
    rationale: str


def propose_mitigations(
    bundle: AuditBundle, catalog: Catalog, adapter: str, llm=None
) -> list[MitigationPlan]:
    plans = []
    for cid, score in rank_findings(bundle, catalog):
        options = mitigations_for(cid, adapter)
        if not options:
            continue
        choice, why = options[0].id, options[0].description
        if llm is not None and len(options) > 1:
            try:
                r = llm.complete(
                    [
                        {
                            "role": "user",
                            "content": f"Control {cid} failed. Choose the best mitigation "
                            f"from {[o.model_dump() for o in options]} and justify briefly.",
                        }
                    ],
                    schema=_Choice.model_json_schema(),
                )
                c = _Choice.model_validate(json.loads(r.content))
                if c.mitigation_id in {o.id for o in options}:
                    choice, why = c.mitigation_id, c.rationale
            except (LLMError, ValueError):
                pass
        plans.append(
            MitigationPlan(
                control_id=cid, mitigation_id=choice, rationale=why, severity_score=score
            )
        )
    return plans
