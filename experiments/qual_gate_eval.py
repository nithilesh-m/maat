"""RQ2 harness: panel verdicts vs gold, inter-judge alpha, flip rate across k runs."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from pathlib import Path

from maat.catalog.loader import load_catalog
from maat.config import load_config
from maat.eval.agreement import cohen_kappa, krippendorff_alpha_ordinal
from maat.eval.gold import load_gold
from maat.evidence.artifacts import ArtifactStore
from maat.evidence.ledger import Ledger
from maat.evidence.signing import RunKey
from maat.gates.engine import policy_bundle_version
from maat.gates.judges import make_judge
from maat.llm.cache import LLMCache
from maat.llm.client import get_judges
from maat.schemas.profile import SystemProfile
from maat.targets.base import Capability
from maat.tools import load_builtin_tools
from maat.tools.contract import ToolContext
from maat.tools.registry import default_registry


class DocsOnly:
    target_id, version_hash = "dossier", "sha256:dossier"

    def capabilities(self):
        return frozenset({Capability.CHAT})


def main(gold_path: Path, runs: int, out: Path) -> dict:
    load_builtin_tools()
    cat, cfg = load_catalog(), load_config()
    cfg.llm_mode = "live"
    items = load_gold(gold_path)
    verdicts = defaultdict(list)
    for k in range(runs):
        with tempfile.TemporaryDirectory() as td:
            judges = get_judges(cfg, LLMCache(Path(td) / "c.sqlite", "live"))
            judge = make_judge(judges, policy_bundle_version(), seed=42 + k)
            for it in items:
                docs = list(it.dossier_docs)
                if it.text:
                    p = Path(td) / f"{it.id}.md"
                    p.write_text(it.text)
                    docs.append(str(p))
                prof = SystemProfile.model_validate(
                    {
                        "profile_version": 1,
                        "name": it.id,
                        "system_type": "rag",
                        "description": "dossier",
                        "intended_use": "n/a",
                        "declared_risk_tier": "high",
                        "target": {"adapter": "chat", "model_family": "none"},
                        "artifacts": {"docs": docs},
                    }
                )
                led = Ledger(Path(td) / f"{it.id}-{k}.sqlite", "q", RunKey.generate())
                ctx = ToolContext(
                    run_id="q",
                    agent="compliance",
                    target=DocsOnly(),
                    ledger=led,
                    artifacts=ArtifactStore(Path(td) / "a", "q"),
                    profile=prof,
                )
                ev = {
                    n: default_registry.get(n)(ctx)
                    for n in ("check_doc_completeness", "check_logging_and_oversight")
                }
                d = judge(cat.controls[it.control_id], ev)
                lab = {"pass": "P" if d.partial else "S", "fail": "N", "not_applicable": "NA"}.get(
                    d.outcome.value, "ABSTAIN"
                )
                verdicts[it.id].append({"label": lab, "votes": [v.label for v in d.judges]})
                led.close()
    first = [verdicts[i.id][0]["label"] for i in items]
    decided = [(f, i.label) for f, i in zip(first, items, strict=True) if f != "ABSTAIN"]
    flips = sum(len({v["label"] for v in verdicts[i.id]}) > 1 for i in items) / len(items)
    alpha = krippendorff_alpha_ordinal(
        list(map(list, zip(*[verdicts[i.id][0]["votes"] for i in items], strict=True)))
    )
    res = {
        "n": len(items),
        "abstention_rate": 1 - len(decided) / len(items),
        "kappa_vs_gold": cohen_kappa([d for d, _ in decided], [g for _, g in decided])
        if decided
        else None,
        "alpha_judges": alpha,
        "flip_rate": flips,
        "verdicts": verdicts,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", type=Path, default=Path("experiments/results/qual_gate.json"))
    a = ap.parse_args()
    print(
        json.dumps(
            {k: v for k, v in main(a.gold, a.runs, a.out).items() if k != "verdicts"}, indent=2
        )
    )
