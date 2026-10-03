import pytest
from typer.testing import CliRunner

import maat.cli as cli
from tests.fakes import FakeChatTarget, vulnerable

runner = CliRunner()


@pytest.fixture
def audited(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "build_target", lambda prof: FakeChatTarget(vulnerable))
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
            "static",
            "--config",
            str(tmp_path / "none.toml"),  # no maat.toml: static tools run without LLM services
        ],
    )
    assert res.exit_code == 0, res.output
    return next(p for p in tmp_path.iterdir() if p.name.startswith("run-"))


@pytest.mark.opa
def test_audit_prints_decisions(audited):
    assert audited.exists()


@pytest.mark.opa
def test_verify_ok(audited):
    res = runner.invoke(cli.app, ["verify", str(audited)])
    assert res.exit_code == 0 and "OK" in res.output


@pytest.mark.opa
def test_render_eu(audited):
    res = runner.invoke(cli.app, ["render", str(audited), "--regime", "EU"])
    assert res.exit_code == 0 and "| AI Act Art. 15(5) | VG-SEC-01 | block |" in res.output


# Review Focus #5
def test_verify_missing_dir_is_clean_failure(tmp_path):
    res = runner.invoke(cli.app, ["verify", str(tmp_path / "nope")])
    assert res.exit_code == 1 and "VERIFICATION FAILED" in res.output
    assert "Traceback" not in res.output


def test_audit_bad_profile_exit_2(tmp_path):
    bad = tmp_path / "p.yaml"
    bad.write_text("name: x\n")
    res = runner.invoke(cli.app, ["audit", "--profile", str(bad), "--out", str(tmp_path)])
    assert res.exit_code == 2 and "error:" in res.output


def test_render_missing_bundle_exit_2(tmp_path):
    res = runner.invoke(cli.app, ["render", str(tmp_path)])
    assert res.exit_code == 2 and "cannot read bundle" in res.output
