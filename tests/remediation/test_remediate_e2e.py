import json

import pytest
from typer.testing import CliRunner

import maat.cli as cli
from maat.evidence.verify import verify_run
from maat.targets.testbed import TestbedTarget
from testbed.rag_bot.app import HARDENED_RULES
from testbed.rag_bot.config import BotConfig
from tests.fakes import CANARY

pytestmark = pytest.mark.opa
runner = CliRunner()

PROFILE = """\
profile_version: 1
name: seeded-bot
system_type: rag
description: Billing bot
intended_use: billing support
declared_risk_tier: limited
target: {adapter: chat, endpoint: "http://x/v1", model: m, model_family: mistral}
artifacts: {qa_set: testbed/rag_bot/qa_set.yaml}
sandbox_allowed: %s
"""


def gullible(messages, cfg):
    """Follows the injected canary unless the system prompt carries the hardening rules."""
    if HARDENED_RULES in messages[0]["content"]:
        return "I can only help with billing questions."
    return CANARY if CANARY in messages[-1]["content"] else "Bills are due on the 5th."


@pytest.fixture
def parent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cli,
        "build_target",
        lambda prof: TestbedTarget(BotConfig(), upstream=gullible, model_family="mistral"),
    )
    prof = tmp_path / "p.yaml"
    prof.write_text(PROFILE % "true")
    res = runner.invoke(
        cli.app,
        ["audit", "--profile", str(prof), "--out", str(tmp_path / "runs"), "--planner", "static",
         "--config", str(tmp_path / "none.toml"), "--as-of", "2026-11-14T10:00:00+00:00"],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    run = next((tmp_path / "runs").iterdir())
    return tmp_path, prof, run


def test_recommendation_only_without_apply(parent):
    tmp, prof, run = parent
    res = runner.invoke(cli.app, ["remediate", str(run), "--profile", str(prof)])
    assert res.exit_code == 0, res.output
    assert "M-HARDEN" in res.output and not (run / "children").exists()


def test_apply_requires_sandbox_flag(parent):
    tmp, prof, run = parent
    ro = tmp / "ro.yaml"
    ro.write_text(PROFILE % "false")
    res = runner.invoke(cli.app, ["remediate", str(run), "--profile", str(ro), "--apply"])
    assert res.exit_code == 2 and "sandbox" in res.output
    assert not (run / "children").exists()


def test_apply_runs_child_audit_and_shows_delta(parent):
    tmp, prof, run = parent
    key = tmp / "k.pem"
    res = runner.invoke(
        cli.app,
        [
            "remediate",
            str(run),
            "--profile",
            str(prof),
            "--apply",
            "--key",
            str(key),
            "--config",
            str(tmp / "none.toml"),
        ],  # fmt: skip
    )
    assert res.exit_code == 0, res.output
    assert "VG-SEC-01" in res.output and "block" in res.output and "pass" in res.output
    assert "delta_AS" in res.output and "utility_before" in res.output
    children = [p for p in (run / "children").iterdir() if p.is_dir()]
    assert len(children) == 1
    assert verify_run(run).ok and verify_run(children[0]).ok
    from maat.evidence.bundle import read_bundle

    parent_b, child_b = read_bundle(run), read_bundle(children[0])
    assert child_b.header.parent_bundle_id == parent_b.header.bundle_id
    child_dec = {d.clause_id: d.outcome.value for d in child_b.decisions}
    parent_dec = {d.clause_id: d.outcome.value for d in parent_b.decisions}
    assert parent_dec["VG-SEC-01"] == "block" and child_dec["VG-SEC-01"] == "pass"
    meta = json.loads((children[0] / "run_meta.json").read_text())
    assert meta["plans"]


def test_remediate_honours_the_same_family_override_like_audits_do(parent):
    from pathlib import Path

    from maat.config import load_config
    from maat.llm.policy import ModelPolicyError
    from maat.profile.loader import load_profile
    from maat.service import remediate_run

    tmp, prof_path, run = parent
    cfg_path = tmp / "m.toml"
    base = load_config().model_copy(deep=True)
    base.profile = "same-family"  # a judge shares the testbed bot's mistral family
    import tomllib  # noqa: F401

    toml = Path("maat.toml").read_text().replace('profile = "local"', 'profile = "same-family"')
    cfg_path.write_text(toml)
    prof = load_profile(prof_path)
    build = lambda p: __import__("maat.targets.testbed", fromlist=["x"]).TestbedTarget(  # noqa: E731
        __import__("testbed.rag_bot.config", fromlist=["x"]).BotConfig(),
        upstream=gullible,
        model_family="mistral",
    )
    with pytest.raises(ModelPolicyError, match="same family"):
        remediate_run(run, prof, apply=True, config=cfg_path, target_builder=build)
    result = remediate_run(
        run, prof, apply=True, config=cfg_path, target_builder=build, allow_same_family_judges=True
    )
    assert result.child_dir is not None
