"""Run attribute-parameterised fairness tools over every sensitive attribute and gate on the
worst result, so a model that is fair on one attribute but biased on another cannot pass."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from maat.schemas.catalog import Control
from maat.schemas.evidence import EvidenceRecord, EvidenceType

ATTRIBUTE_TOOLS = ("tabular_group_metrics", "find_proxy_features")


def sensitive_attributes_present(profile, target) -> list[str]:
    cols = set(getattr(getattr(target, "data", None), "columns", []))
    return [a for a in profile.sensitive_attributes if a in cols]


def call_sweeping(spec, make_ctx: Callable[[], Any], args: dict, attributes: list[str]):
    """One record per sensitive attribute for attribute tools; a single record otherwise."""
    if spec.name in ATTRIBUTE_TOOLS and attributes:
        return [spec(make_ctx(), **{**args, "attribute": a}) for a in attributes]
    return [spec(make_ctx(), **args)]


def worst_for(control: Control, candidates: list[EvidenceRecord]) -> EvidenceRecord:
    """The measured candidate that is worst for this control's predicate (else the last one)."""
    pred = control.predicate
    scored = []
    for r in candidates:
        if r.evidence_type is not EvidenceType.MEASURED or pred is None:
            continue
        v = r.result.get("metrics", {}).get(pred.metric)
        if isinstance(v, int | float) and not isinstance(v, bool):
            scored.append((float(v), r))
    if not scored:
        return candidates[-1]
    pick = min if pred.op == "ge" else max
    return pick(scored, key=lambda t: t[0])[1]
