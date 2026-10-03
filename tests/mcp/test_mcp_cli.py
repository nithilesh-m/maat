import asyncio

import pytest
from typer.testing import CliRunner

import maat.cli as cli
from maat.evidence.bundle import read_bundle
from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from maat.mcp.server import build_server
from maat.profile.loader import load_profile
from maat.runner import tool_context
from tests.fakes import FakeChatTarget, vulnerable

pytestmark = pytest.mark.opa
runner = CliRunner()


def test_serve_session_then_seal_produces_verifiable_incomplete_bundle(tmp_path, monkeypatch):
    prof = load_profile("examples/profiles/support_bot.yaml")
    target = FakeChatTarget(vulnerable)
    key_path = tmp_path / "k.pem"
    RunKey.generate().save_pem(key_path)
    cfg, handles = cli.open_mcp_run(
        prof, target, tmp_path / "runs", RunKey.load_pem(key_path), "risk"
    )
    server = build_server("risk", lambda a: tool_context(cfg, handles, a, target, prof))
    asyncio.run(server.call_tool("probe_prompt_injection", {"split": "dev"}))
    handles.ledger.close()

    monkeypatch.setattr(cli, "build_target", lambda p: FakeChatTarget(vulnerable))
    res = runner.invoke(cli.app, ["mcp", "seal", str(cfg.run_dir), "--key", str(key_path)])
    assert res.exit_code == 0, res.output
    assert "VG-SEC-01" in res.output and "block" in res.output
    assert verify_run(cfg.run_dir).ok
    bundle = read_bundle(cfg.run_dir)
    assert bundle.status == "incomplete"  # other applicable controls have no evidence yet
    assert {d.clause_id for d in bundle.decisions} >= {"VG-SEC-01"}


def test_seal_on_missing_run_fails_cleanly(tmp_path):
    res = runner.invoke(cli.app, ["mcp", "seal", str(tmp_path / "nope")])
    assert res.exit_code == 2 and "Traceback" not in res.output


def test_serve_rejects_unknown_agent(tmp_path):
    res = runner.invoke(
        cli.app,
        ["mcp", "serve", "--agent", "wizard", "--profile", "examples/profiles/support_bot.yaml",
         "--out", str(tmp_path)],
    )  # fmt: skip
    assert res.exit_code == 2 and "agent" in res.output
