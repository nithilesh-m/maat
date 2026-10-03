from __future__ import annotations

from collections import defaultdict

from maat.schemas.bundle import BundleEntry
from maat.schemas.catalog import Catalog, ClauseRow
from maat.schemas.decisions import GateOutcome
from maat.schemas.evidence import EvidenceType


def _applicable(rows: list[ClauseRow]) -> list[ClauseRow]:
    return [r for r in rows if r.outcome is not GateOutcome.NOT_APPLICABLE]


def _covered(r: ClauseRow) -> bool:
    return r.adequacy > 0 or r.outcome is GateOutcome.WAIVE


def clause_coverage(rows: list[ClauseRow]) -> float:
    app = _applicable(rows)
    return sum(1 for r in app if _covered(r)) / len(app) if app else 0.0


def adequacy_score(rows: list[ClauseRow]) -> float:
    app = _applicable(rows)
    return sum(min(r.adequacy, 3) for r in app) / (3 * len(app)) if app else 0.0


def measured_evidence_ratio(rows: list[ClauseRow], entries: list[BundleEntry]) -> float:
    measured = {e.record_id for e in entries if e.evidence_type is EvidenceType.MEASURED}
    covered = [r for r in _applicable(rows) if _covered(r)]
    if not covered:
        return 0.0
    hits = sum(1 for r in covered if any(k.record_id in measured for k in r.evidence))
    return hits / len(covered)


def dimension_scores(rows: list[ClauseRow], catalog: Catalog) -> dict[str, float]:
    groups: dict[str, list[ClauseRow]] = defaultdict(list)
    for r in rows:
        groups[catalog.controls[r.control_id].dimension].append(r)
    return {dim: adequacy_score(rs) for dim, rs in sorted(groups.items())}


def reuse_factor(rows: list[ClauseRow]) -> float:
    """GEAP Eq. 3: the share of distinct evidence records that support two or more clause rows."""
    uses: dict[str, int] = {}
    for r in rows:
        for rid in {link.record_id for link in r.evidence}:
            uses[rid] = uses.get(rid, 0) + 1
    return sum(1 for k in uses.values() if k >= 2) / len(uses) if uses else 0.0
