from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from maat.catalog.loader import load_catalog
from maat.evidence.bundle import read_bundle
from maat.gates.engine import policy_bundle_version
from maat.gates.judges import make_judge
from maat.schemas.bundle import AuditBundle
from maat.schemas.evidence import EvidenceRecord

FILLER = " Additional context: the system operates in a retail billing environment." * 6


def flip_rate(bundles: list[AuditBundle]) -> pd.DataFrame:
    """Per control: the outcomes across repeats and whether they flipped. Rego controls should be
    stable unless the evidence changed; the paper reports both kinds either way."""
    by: dict[str, list] = {}
    for b in bundles:
        for d in b.decisions:
            by.setdefault(d.clause_id, []).append(d)
    rows = []
    for cid, ds in sorted(by.items()):
        outs = [d.outcome.value for d in ds]
        rows.append(
            {
                "control_id": cid,
                "method": ds[0].method,
                "outcomes": "|".join(outs),
                "flipped": len(set(outs)) > 1,
                "n": len(outs),
            }
        )
    return pd.DataFrame(rows)


def _records(run_dir: Path) -> dict[str, EvidenceRecord]:
    c = sqlite3.connect(f"file:{run_dir / 'ledger.sqlite'}?mode=ro", uri=True)
    try:
        return {
            r.id: r
            for r in (
                EvidenceRecord.model_validate_json(b)
                for (b,) in c.execute("SELECT body FROM evidence")
            )
        }
    finally:
        c.close()


def _pad(r: EvidenceRecord) -> EvidenceRecord:
    samples = list(r.result.get("samples") or []) + [{"note": FILLER}]
    return r.model_copy(update={"result": {**r.result, "samples": samples}})


def perturb_judgments(
    run_dir: Path, judges, kinds=("order", "verbosity"), seeds=range(5)
) -> pd.DataFrame:
    """Re-run the judge panel over the same recorded evidence with the evidence reordered (order)
    or padded with neutral filler (verbosity) and report how often the verdict changes."""
    run_dir = Path(run_dir)
    b, cat, recs = read_bundle(run_dir), load_catalog(), _records(run_dir)
    rows = []
    for d in b.decisions:
        if d.method != "judge_panel":
            continue
        control = cat.controls[d.clause_id]
        ev = {recs[i].tool.split("@")[0]: recs[i] for i in d.inputs if i in recs}
        for kind in kinds:
            for s in seeds:
                use = {k: _pad(v) for k, v in ev.items()} if kind == "verbosity" else ev
                nd = make_judge(judges, policy_bundle_version(), seed=1000 + s)(control, use)
                rows.append(
                    {
                        "run": run_dir.name,
                        "control_id": d.clause_id,
                        "kind": kind,
                        "seed": s,
                        "original": d.outcome.value,
                        "perturbed": nd.outcome.value,
                        "changed": nd.outcome != d.outcome or nd.partial != d.partial,
                    }
                )
    return pd.DataFrame(rows)
