from __future__ import annotations

from maat.catalog.metrics import adequacy_score, clause_coverage, measured_evidence_ratio
from maat.schemas.bundle import AuditBundle, BundleEntry
from maat.schemas.catalog import Catalog, ClauseRow, Control, EvidenceLink
from maat.schemas.decisions import GateDecision, GateOutcome
from maat.schemas.evidence import EvidenceType
from maat.schemas.findings import Finding, FindingStatus

_ZERO = {GateOutcome.BLOCK, GateOutcome.FAIL, GateOutcome.ABSTAIN, GateOutcome.NOT_APPLICABLE}


class VersionMismatchError(RuntimeError):
    pass


def adequacy(
    control: Control, decision: GateDecision, entries: list[BundleEntry], findings: list[Finding]
) -> int:
    if decision.outcome in _ZERO:
        return 0
    if decision.outcome is GateOutcome.WAIVE:
        return 1
    if control.kind == "qualitative":
        return 1 if decision.partial else 2
    linked = [e for e in entries if control.id in e.clause_ids]
    measured = [e for e in linked if e.evidence_type is EvidenceType.MEASURED]
    if not measured:
        soft = {EvidenceType.LLM_JUDGMENT, EvidenceType.MANUAL_NEEDED}
        return 1 if any(e.evidence_type in soft for e in linked) else 0
    weights = {e.tool: e.w for e in control.evidence_edges}
    max_w = max(weights.get(e.tool.split("@", 1)[0], 0) for e in measured)
    mine = [f for f in findings if control.id in f.clause_ids]
    if max_w == 3 and all(f.status is FindingStatus.CONFIRMED for f in mine):
        return 3
    return 2


def render_view(
    bundle: AuditBundle, catalog: Catalog, regime: str, policy_version: str
) -> list[ClauseRow]:
    v = bundle.header.versions
    if v.get("catalog") != catalog.version:
        raise VersionMismatchError(
            f"bundle catalog version {v.get('catalog')} != supplied catalog {catalog.version}"
        )
    if v.get("policies") != policy_version:
        raise VersionMismatchError(
            f"bundle policies version {v.get('policies')} != supplied policies {policy_version}"
        )
    rows: list[ClauseRow] = []
    for d in bundle.decisions:
        control = catalog.controls.get(d.clause_id)
        if control is None:
            raise VersionMismatchError(f"control {d.clause_id} not in supplied catalog")
        a = adequacy(control, d, bundle.entries, bundle.findings)
        links = [
            EvidenceLink(record_id=e.record_id, hash=e.hash)
            for e in bundle.entries
            if control.id in e.clause_ids
        ]
        for clause in control.regimes.get(regime, []):
            rows.append(
                ClauseRow(
                    regime=regime,
                    regime_clause=clause,
                    control_id=control.id,
                    adequacy=a,
                    outcome=d.outcome,
                    evidence=links,
                    waiver_id=d.waiver_id,
                )
            )
    return sorted(rows, key=lambda r: (r.regime_clause, r.control_id))


def render_markdown(rows: list[ClauseRow], *, regime: str, bundle: AuditBundle) -> str:
    lines = [f"# {regime} view - bundle {bundle.header.bundle_id}", ""]
    if not rows:
        lines.append(f"No controls in this bundle map to regime {regime}.")
        return "\n".join(lines) + "\n"
    lines += ["| Regime clause | Control | Outcome | a_c | Evidence |", "|---|---|---|---|---|"]
    for r in rows:
        ev = ", ".join(f"{k.record_id} ({k.hash[:15]})" for k in r.evidence) or "-"
        lines.append(
            f"| {r.regime_clause} | {r.control_id} | {r.outcome.value} | {r.adequacy} | {ev} |"
        )
    lines += [
        "",
        f"CC = {clause_coverage(rows):.3f}",
        f"AS = {adequacy_score(rows):.3f}",
        f"MER = {measured_evidence_ratio(rows, bundle.entries):.3f}",
    ]
    return "\n".join(lines) + "\n"
