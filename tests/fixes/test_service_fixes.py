"""Regression tests for review findings I3, I4, I6, I7."""

import base64
import json

import pytest
from typer.testing import CliRunner

import maat.cli as cli
import maat.service as service
from maat.config import load_config
from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from maat.gates.engine import OpaEngine
from maat.llm.cache import CacheMiss
from maat.llm.policy import ModelPolicyError
from maat.llm.untrusted import NullScreen
from maat.runner import RunConfig, run_audit
from maat.schemas.decisions import GateDecision, GateOutcome, JudgeVote
from maat.schemas.evidence import EvidenceType
from maat.service import AuditOptions
from tests.fakes import AS_OF, SEED, FakeChatTarget, fixed_clock, make_profile, robust, seq_ids

pytestmark = pytest.mark.opa


def test_i4_static_planner_enforces_model_policy(tmp_path):
    cfg = load_config().model_copy(deep=True)
    cfg.models["local"] = cfg.models["local"].model_copy(
        update={"specialists": "openai_compat:claude-sonnet-5-5"}
    )
    run_cfg = RunConfig(run_id="r", run_dir=tmp_path / "r", signer=RunKey.generate(), as_of=AS_OF)
    with pytest.raises(ModelPolicyError, match="local_only"):
        service.execute_audit(
            make_profile(),
            FakeChatTarget(robust),
            run_cfg,
            cfg,
            AuditOptions(planner="static"),
            NullScreen(),
        )
    assert not (tmp_path / "r").exists()  # refused before any run was opened


def _stub_judge(control, evidence):
    return GateDecision(
        clause_id=control.id, gate=control.gate, method="judge_panel", policy_version="p",
        outcome=GateOutcome.PASS, rationale="panel", agreement=1.0,
        judges=[JudgeVote(model="m", label="S", confidence=0.9, cited=["x"])],
    )  # fmt: skip


def test_i6_judge_verdicts_are_ledger_evidence(tmp_path):
    cfg = RunConfig(
        run_id="run-j", run_dir=tmp_path / "r", signer=RunKey.from_seed(SEED), as_of=AS_OF,
        clock=fixed_clock(), id_factory=seq_ids(),
    )  # fmt: skip
    from maat.catalog.loader import load_catalog

    b = run_audit(
        make_profile(), FakeChatTarget(robust), load_catalog(), OpaEngine(), cfg, judge=_stub_judge
    )
    judgments = [e for e in b.entries if e.evidence_type is EvidenceType.LLM_JUDGMENT]
    assert judgments and all(e.tool == "judge_panel" and e.clause_ids for e in judgments)
    assert verify_run(tmp_path / "r").ok


def test_i6_judge_cache_miss_is_not_swallowed():
    from tests.gates.test_judges import C, R, make_judge

    class Missing:
        ref = type("R", (), {"name": "m"})

        def complete(self, messages, *, tools=None, schema=None):
            raise CacheMiss("not recorded")

    with pytest.raises(CacheMiss):
        make_judge([Missing()] * 3, "p")(C, {"check_logging_and_oversight": R})


def _static_run(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "build_target", lambda p: FakeChatTarget(robust))
    monkeypatch.setattr(service, "build_target", lambda p: FakeChatTarget(robust))
    res = CliRunner().invoke(
        cli.app,
        ["audit", "--profile", "examples/profiles/support_bot.yaml", "--out", str(tmp_path / "o"),
         "--planner", "static", "--config", str(tmp_path / "none.toml"),
         "--as-of", "2026-11-14T10:00:00+00:00"],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    return next((tmp_path / "o").iterdir())


def test_i6_replay_detects_changed_decisions_even_if_bundle_id_matches(tmp_path, monkeypatch):
    run = _static_run(tmp_path, monkeypatch)
    ok, msg = service.replay_audit(run, tmp_path / "rp", lambda p: FakeChatTarget(robust))
    assert ok, msg
    env = json.loads((run / "bundle.dsse.json").read_text())
    stmt = json.loads(base64.b64decode(env["payload"]))
    stmt["predicate"]["decisions"][0]["rationale"] = "edited after the fact"
    env["payload"] = base64.b64encode(json.dumps(stmt).encode()).decode()
    (run / "bundle.dsse.json").write_text(json.dumps(env))
    ok, msg = service.replay_audit(run, tmp_path / "rp2", lambda p: FakeChatTarget(robust))
    assert not ok and msg.startswith("DIVERGED") and "decisions" in msg


def test_i3_replaying_twice_does_not_report_false_divergence(tmp_path, monkeypatch):
    run = _static_run(tmp_path, monkeypatch)
    out = tmp_path / "same-out-dir"
    for _ in range(2):
        ok, msg = service.replay_audit(run, out, lambda p: FakeChatTarget(robust))
        assert ok, msg


def test_i7_non_terminal_runs_are_failed_on_startup(tmp_path):
    from maat.api.app import create_app
    from maat.api.settings import ApiSettings
    from maat.api.store import RunStore

    runs = tmp_path / "runs"
    store = RunStore(runs / "runs.db")
    for rid, status in (("a", "queued"), ("b", "running"), ("c", "paused"), ("d", "complete")):
        store.create(rid, runs / rid, "p.yaml", "static", "u")
        store.set_status(rid, status)
    app = create_app(ApiSettings(runs_dir=runs, users_file=tmp_path / "u.toml"))
    got = {r["run_id"]: (r["status"], r["error"]) for r in app.state.store.list()}
    assert got["a"][0] == got["b"][0] == "failed" and "restart" in got["a"][1]
    assert got["c"][0] == "paused" and got["d"][0] == "complete"  # paused is resumable
