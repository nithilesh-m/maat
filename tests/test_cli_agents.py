import pytest
from typer.testing import CliRunner

import maat.cli as cli
import maat.service as service
from tests.agents.test_orchestrator import Fake
from tests.fakes import FakeChatTarget, vulnerable

pytestmark = pytest.mark.opa

runner = CliRunner()


@pytest.fixture
def agent_run(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "build_target", lambda prof: FakeChatTarget(vulnerable))
    monkeypatch.setattr(service, "llm_factory", lambda role, cache, cfg: Fake())
    monkeypatch.setattr(service, "get_judges", lambda cfg, cache: [])  # no Ollama in unit tests
    res = runner.invoke(
        cli.app,
        [
            "audit",
            "--profile",
            "examples/profiles/support_bot.yaml",
            "--out",
            str(tmp_path),
            "--as-of",
            "2026-11-14T10:00:00+00:00",
            "--planner",
            "agents",
            "--auto-approve",
            "--no-screen",
        ],
    )
    assert res.exit_code == 0, res.output
    return next(p for p in tmp_path.iterdir() if p.name.startswith("run-"))


def test_agent_audit_writes_meta_and_run_copies(agent_run):
    assert (agent_run / "run_meta.json").exists()
    assert (agent_run / "profile.yaml").exists()
    assert (agent_run / "maat.toml").exists()
    assert (agent_run / "llm_cache.sqlite").exists()


def test_replay_matches_original_bundle_id(agent_run, tmp_path):
    res = runner.invoke(cli.app, ["replay", str(agent_run), "--out", str(tmp_path / "replays")])
    assert res.exit_code == 0, res.output
    assert "MATCH" in res.output


def test_verify_agent_run(agent_run):
    res = runner.invoke(cli.app, ["verify", str(agent_run)])
    assert res.exit_code == 0 and "OK" in res.output
