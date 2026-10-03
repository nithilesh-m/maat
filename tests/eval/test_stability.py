import json
import re

import pytest

from maat.eval.stability import flip_rate, perturb_judgments
from maat.llm.client import LLMResponse
from maat.schemas.decisions import GateOutcome
from tests.catalog.test_c2at import E_INJ, bundle, dec


def test_flip_rate():
    b1 = bundle([dec("VG-SEC-01", GateOutcome.BLOCK)], [E_INJ])
    b2 = bundle([dec("VG-SEC-01", GateOutcome.PASS)], [E_INJ])
    b3 = bundle([dec("VG-SEC-01", GateOutcome.BLOCK)], [E_INJ])
    df = flip_rate([b1, b2, b3])
    row = df[df.control_id == "VG-SEC-01"].iloc[0]
    assert row.flipped and row.outcomes == "block|pass|block" and row.method == "rego"


def test_stable_decisions_do_not_flip():
    b = bundle([dec("VG-SEC-01", GateOutcome.BLOCK)], [E_INJ])
    row = flip_rate([b, b, b]).iloc[0]
    assert not row.flipped and row.n == 3


class FixedJudge:
    def __init__(self, label, bias_on_long=None):
        self.label, self.bias_on_long = label, bias_on_long
        self.ref = type("R", (), {"name": f"j-{label}"})

    def complete(self, messages, *, tools=None, schema=None):
        text = messages[-1]["content"]
        m = re.search(r'"record_id": "([^"]+)"', text)
        rid = m.group(1) if m else None  # a control with no evidence has nothing to cite
        label = self.bias_on_long if self.bias_on_long and "retail billing" in text else self.label
        return LLMResponse(
            model="j",
            cache_key="k",
            content=json.dumps(
                {
                    "label": label,
                    "cited_record_ids": [rid] if rid else [],
                    "cited_spans": [],
                    "confidence": 0.9,
                    "rationale": "r",
                }
            ),
        )


@pytest.fixture
def judged_run(tmp_path):
    """A sealed static run whose qualitative controls were judged by a stable 'S' panel."""
    from maat.catalog.loader import load_catalog
    from maat.evidence.signing import RunKey
    from maat.gates.engine import OpaEngine
    from maat.gates.judges import make_judge
    from maat.runner import RunConfig, run_audit
    from tests.fakes import AS_OF, SEED, FakeChatTarget, fixed_clock, make_profile, robust, seq_ids

    judge = make_judge([FixedJudge("S")] * 3, OpaEngine().policy_version)
    cfg = RunConfig(
        run_id="run-p", run_dir=tmp_path / "run-p", signer=RunKey.from_seed(SEED), as_of=AS_OF,
        clock=fixed_clock(), id_factory=seq_ids(),
    )  # fmt: skip
    run_audit(make_profile(), FakeChatTarget(robust), load_catalog(), OpaEngine(), cfg, judge=judge)
    return tmp_path / "run-p"


@pytest.mark.opa
def test_perturbation_leaves_a_robust_panel_unchanged(judged_run):
    df = perturb_judgments(judged_run, [FixedJudge("S")] * 3, seeds=range(2))
    assert not df.empty and set(df.kind) == {"order", "verbosity"}
    assert df.changed.sum() == 0


@pytest.mark.opa
def test_verbosity_sensitive_panel_is_detected(judged_run):
    biased = [FixedJudge("S", bias_on_long="N")] * 3  # flips when the evidence is padded
    df = perturb_judgments(judged_run, biased, kinds=("verbosity",), seeds=range(2))
    judged = df[df.original == "pass"]  # controls without evidence abstain and cannot flip
    assert not judged.empty and judged.changed.all() and (judged.perturbed == "fail").all()


@pytest.mark.opa
def test_analyze_rq2_writes_flip_perturb_and_summary(tmp_path, judged_run):
    import json as _json

    import pandas as pd

    from experiments.analyze_rq2 import analyze

    idx = tmp_path / "index.csv"
    pd.DataFrame(
        [
            {"cell_id": f"t1_seeded__maat__r{i}", "status": "complete", "run_dir": str(judged_run)}
            for i in range(3)
        ]
    ).to_csv(idx, index=False)
    qual = tmp_path / "qual.json"
    qual.write_text(
        _json.dumps(
            {
                "n": 4,
                "kappa_vs_gold": 0.7,
                "alpha_judges": 0.8,
                "abstention_rate": 0.1,
                "flip_rate": 0.05,
            }
        )
    )
    out = tmp_path / "out"
    summary = analyze(idx, out, [FixedJudge("S")] * 3, qual)
    metrics = set(summary.metric)
    assert {"flip_rate_rego", "perturb_change_rate_order", "qual_gate_kappa_vs_gold"} <= metrics
    assert (
        float(summary[summary.metric == "flip_rate_rego"].value.iloc[0]) == 0.0
    )  # same run thrice
    for f in ("rq2_flip.csv", "rq2_perturb.csv", "rq2_summary.csv"):
        assert (out / f).exists()
