"""Regression tests for the whole-branch review findings (C3, C4, I1, I5, I6, I8)."""

import json
import sqlite3
import threading
from datetime import timedelta

import pytest

from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from maat.review.queue import (
    ReviewInputError,
    Waiver,
    add_waiver,
    pending_reviews,
    record_human_decision,
)
from tests.fakes import AS_OF, robust, vulnerable
from tests.test_runner import audit

pytestmark = pytest.mark.opa
KEY = RunKey.from_seed(b"\x05" * 32)


def _waiver(clause):
    return Waiver(
        id="W-1", clause_id=clause, owner="o", scope="s",
        expiry=AS_OF + timedelta(days=3), compensations=[],
    )  # fmt: skip


@pytest.mark.parametrize("clause", ["NOPE-1", "DG-DATA-01"])  # unknown, qualitative
def test_c3_invalid_waiver_is_rejected_and_run_still_verifies(tmp_path, clause):
    audit(tmp_path / "r", vulnerable)
    with pytest.raises(ReviewInputError):
        add_waiver(tmp_path / "r", _waiver(clause), KEY, AS_OF)
    assert verify_run(tmp_path / "r").ok


def test_c4_human_review_cannot_override_measured_decisions(tmp_path):
    audit(tmp_path / "r", vulnerable)  # VG-SEC-01 is a measured block
    with pytest.raises(ReviewInputError, match="abstain"):
        record_human_decision(tmp_path / "r", "VG-SEC-01", "S", "x", "looks fine", KEY, AS_OF)
    with pytest.raises(ReviewInputError):
        record_human_decision(tmp_path / "r", "NOPE-1", "S", "x", "y", KEY, AS_OF)
    assert verify_run(tmp_path / "r").ok


def test_i1_concurrent_reviews_are_serialised_without_lost_updates(tmp_path):
    audit(tmp_path / "r", robust)
    clauses = [d.clause_id for d in pending_reviews(tmp_path / "r")][:6]
    errors: list[Exception] = []

    def go(clause):
        try:
            record_human_decision(tmp_path / "r", clause, "S", "r", "ok", KEY, AS_OF)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=go, args=(c,)) for c in clauses]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors, errors
    from maat.evidence.bundle import read_bundle

    humans = [d for d in read_bundle(tmp_path / "r").decisions if d.method == "human"]
    assert sorted(d.clause_id for d in humans) == sorted(clauses)
    assert verify_run(tmp_path / "r").ok


def test_i5_llm_cannot_choose_gating_parameters(tmp_path):
    from maat.agents.base import AgentBudget, run_specialist
    from maat.catalog.loader import load_catalog
    from maat.llm.untrusted import NullScreen
    from maat.tools import load_builtin_tools
    from maat.tools.registry import default_registry
    from tests.agents.test_specialist import Scripted, resp
    from tests.fakes import FakeChatTarget, ctx_with

    load_builtin_tools()
    ctx = ctx_with(tmp_path, FakeChatTarget(vulnerable))
    llm = Scripted(
        [
            resp(calls=[("probe_prompt_injection", {"split": "heldout", "limit": 1})]),
            resp(),
            resp('{"findings": []}'),
        ]
    )
    res = run_specialist(
        agent="risk", system_prompt="s", controls=[load_catalog().controls["VG-SEC-01"]],
        specs=[default_registry.get("probe_prompt_injection")], make_ctx=lambda: ctx, llm=llm,
        budget=AgentBudget(), screen=NullScreen(),
        static_params={"probe_prompt_injection": {"split": "dev"}},
    )  # fmt: skip
    assert res.records[0].params == {"split": "dev"}
    assert res.records[0].result["metrics"]["n"] == 14


def test_i8_static_fairness_gates_on_the_worst_sensitive_attribute(tmp_path):
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression

    from maat.catalog.loader import load_catalog
    from maat.evidence.signing import RunKey as RK
    from maat.gates.engine import OpaEngine
    from maat.runner import RunConfig, run_audit
    from maat.targets.tabular import TabularTarget
    from tests.fakes import SEED, fixed_clock, make_profile, seq_ids

    rng = np.random.default_rng(0)
    df = pd.DataFrame({"x": rng.normal(size=600), "SEX": rng.integers(1, 3, 600)})
    df["RACE"] = (df.x > 0).astype(int) + 1  # strongly tied to the outcome, SEX is not
    df["y"] = (df.x > 0).astype(int)
    model = LogisticRegression().fit(df[["x", "SEX", "RACE"]], df.y)
    target = TabularTarget("tab", model, df, "y", 1, ["x", "SEX", "RACE"])
    prof = make_profile(
        system_type="tabular_ml", declared_risk_tier="high",
        sensitive_attributes=["SEX", "RACE"],
        target={"adapter": "tabular", "model_family": "sklearn"},
    )  # fmt: skip
    cfg = RunConfig(
        run_id="run-f", run_dir=tmp_path / "r", signer=RK.from_seed(SEED), as_of=AS_OF,
        clock=fixed_clock(), id_factory=seq_ids(),
    )  # fmt: skip
    b = run_audit(prof, target, load_catalog(), OpaEngine(), cfg)
    d = next(x for x in b.decisions if x.clause_id == "VG-FAIR-01")
    assert d.outcome.value == "block" and "dp_diff=" in d.rationale
    conn = sqlite3.connect(tmp_path / "r" / "ledger.sqlite")
    rows = [json.loads(r[0]) for r in conn.execute("SELECT body FROM evidence")]
    tried = {r["params"].get("attribute") for r in rows if r["tool"].startswith("tabular_group")}
    assert tried == {"SEX", "RACE"}
    assert float(d.rationale.split("dp_diff=")[1].split()[0]) > 0.5  # RACE (worst), not SEX
