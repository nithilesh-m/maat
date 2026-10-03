# ruff: noqa: E501
import json
import sqlite3

import pytest

from maat.catalog.metrics import reuse_factor
from maat.eval.cost import cost_rows
from maat.eval.quality import KINDS, tamper_trials
from maat.schemas.catalog import ClauseRow, EvidenceLink
from tests.fakes import vulnerable
from tests.test_runner import audit


def _link(i):
    return EvidenceLink(record_id=i, hash="h")


def test_reuse_factor():
    rows = [
        ClauseRow(
            regime="EU",
            regime_clause="a",
            control_id="X-A-01",
            adequacy=2,
            outcome="pass",
            evidence=[_link("r1")],
        ),
        ClauseRow(
            regime="EU",
            regime_clause="b",
            control_id="X-A-02",
            adequacy=2,
            outcome="pass",
            evidence=[_link("r1"), _link("r2")],
        ),
    ]
    assert reuse_factor(rows) == 0.5
    assert reuse_factor([]) == 0.0


@pytest.mark.opa
def test_tamper_all_detected(tmp_path):
    audit(tmp_path / "r", vulnerable)
    df = tamper_trials(tmp_path / "r", n=20, seed=1)
    assert df.detected.all() and set(df.kind) >= {"record_body", "artifact_bytes"}
    assert set(df.kind) <= set(KINDS)


@pytest.mark.opa
def test_tamper_trials_never_touch_the_original_run(tmp_path):
    from maat.evidence.verify import verify_run

    audit(tmp_path / "r", vulnerable)
    tamper_trials(tmp_path / "r", n=10, seed=2)
    assert verify_run(tmp_path / "r").ok


@pytest.mark.opa
def test_quality_rows_report_the_four_metrics_per_regime(tmp_path):
    from maat.catalog.loader import load_catalog
    from maat.eval.quality import quality_rows

    audit(tmp_path / "r", vulnerable)
    q = quality_rows(tmp_path / "r", load_catalog())
    assert "EU" in q and set(q["EU"]) == {"cc", "as", "mer", "rf"}
    assert all(0 <= v <= 1 for v in q["EU"].values())


def test_cost(tmp_path):
    (tmp_path / "ledger.sqlite").touch()
    c = sqlite3.connect(tmp_path / "llm_cache.sqlite")
    c.execute("CREATE TABLE llm_cache (key TEXT, request TEXT, response TEXT)")
    c.execute(
        "INSERT INTO llm_cache VALUES ('k','{}',?)",
        (json.dumps({"prompt_eval_count": 10, "eval_count": 5}),),
    )
    c.commit()
    c.close()
    r = cost_rows(tmp_path)
    assert r["prompt_tokens"] == 10 and r["completion_tokens"] == 5 and r["llm_calls"] == 1


@pytest.mark.opa
def test_cost_wall_clock_from_the_ledger(tmp_path):
    audit(tmp_path / "r", vulnerable)
    r = cost_rows(tmp_path / "r")
    assert r["wall_clock_s"] > 0 and r["gpu_hours_est"] == r["wall_clock_s"] / 3600
    assert r["llm_calls"] == 0  # a static run makes no LLM calls


@pytest.mark.opa
def test_replay_check_matches_for_an_untouched_run(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    import maat.cli as cli
    import maat.service as service
    from maat.eval.quality import replay_check
    from tests.fakes import FakeChatTarget, robust

    monkeypatch.setattr(cli, "build_target", lambda p: FakeChatTarget(robust))
    monkeypatch.setattr(service, "build_target", lambda p: FakeChatTarget(robust))
    res = CliRunner().invoke(
        cli.app,
        [
            "audit",
            "--profile",
            "examples/profiles/support_bot.yaml",
            "--out",
            str(tmp_path / "o"),
            "--planner",
            "static",
            "--config",
            str(tmp_path / "none.toml"),
        ],
    )
    assert res.exit_code == 0, res.output
    run = next((tmp_path / "o").iterdir())
    out = replay_check(run, tmp_path / "rp")
    assert out["match"] is True and out["error"] is None
    assert replay_check(tmp_path / "missing", tmp_path / "rp2")["match"] is False


@pytest.mark.opa
def test_run_rq4_writes_all_four_files_with_full_tamper_detection(tmp_path, monkeypatch):
    import pandas as pd
    from typer.testing import CliRunner

    import maat.cli as cli
    import maat.service as service
    from experiments.run_rq4 import run
    from tests.fakes import FakeChatTarget, robust

    monkeypatch.setattr(cli, "build_target", lambda p: FakeChatTarget(robust))
    monkeypatch.setattr(service, "build_target", lambda p: FakeChatTarget(robust))
    res = CliRunner().invoke(
        cli.app,
        [
            "audit",
            "--profile",
            "examples/profiles/support_bot.yaml",
            "--out",
            str(tmp_path / "o"),
            "--planner",
            "static",
            "--config",
            str(tmp_path / "none.toml"),
        ],
    )
    assert res.exit_code == 0, res.output
    runp = next((tmp_path / "o").iterdir())
    idx = tmp_path / "index.csv"
    pd.DataFrame(
        [
            {
                "cell_id": "t1_seeded__b0__r0",
                "condition": "b0",
                "status": "complete",
                "run_dir": str(runp),
            }
        ]
    ).to_csv(idx, index=False)
    summary = run(idx, tmp_path / "out", trials=10)
    assert summary["tamper_detection_rate"] == 1.0 and summary["replay_match_rate"] == 1.0
    for f in ("rq4_quality.csv", "rq4_tamper.csv", "rq4_replay.csv", "rq4_cost.csv"):
        assert (tmp_path / "out" / f).exists()
