from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from maat.evidence.bundle import read_bundle
from maat.runner import RunConfig, run_audit
from maat.schemas.bundle import AuditBundle
from maat.schemas.catalog import Catalog
from maat.schemas.remediation import MitigationPlan

HELDOUT = {
    n: {"split": "heldout"}
    for n in (
        "probe_prompt_injection",
        "probe_jailbreak",
        "scan_pii_leakage",
        "counterfactual_swap_test",
        "output_consistency",
        "probe_ai_disclosure",
    )
}
UTILITY = {"testbed": "task_utility", "tabular": "tabular_performance"}


def retest(
    parent_run_dir: Path,
    child_target,
    profile,
    plans: list[MitigationPlan],
    catalog: Catalog,
    engine,
    signer,
    out_dir: Path,
    adapter: str,
    baseline_target=None,
    services=None,
) -> tuple[AuditBundle, AuditBundle, Path]:
    """Static child audit of the mitigated snapshot, scoped to the mitigated controls plus the
    utility tool, on the held-out probe split. Returns (parent, child, child_run_dir)."""
    parent = read_bundle(parent_run_dir)
    scoped = {p.control_id for p in plans}
    sub = Catalog(
        version=catalog.version,
        controls={k: v for k, v in catalog.controls.items() if k in scoped},
    )
    now = datetime.now(UTC)
    run_id = f"{parent.header.run_id}-child-{now:%H%M%S}"
    cfg = RunConfig(
        run_id=run_id,
        run_dir=Path(out_dir) / run_id,
        signer=signer,
        as_of=now,
        tool_params=HELDOUT,
        services=services,
        meta={"parent_run": str(parent_run_dir), "plans": [p.model_dump() for p in plans]},
    )
    child = run_audit(
        profile,
        child_target,
        sub,
        engine,
        cfg,
        parent_bundle_id=parent.header.bundle_id,
        extra_tools=[UTILITY[adapter]],
        baseline_target=baseline_target,
    )
    return parent, child, cfg.run_dir
