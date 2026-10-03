import pytest
from typer.testing import CliRunner

import maat.cli as cli
import maat.service as service
from maat.evidence.bundle import read_bundle
from maat.evidence.verify import verify_run
from tests.api.test_auth_store import H, app_with
from tests.api.test_runs_sse import PROFILE, wait
from tests.fakes import FakeChatTarget, vulnerable

pytestmark = pytest.mark.opa


def _comparable(bundle):
    return sorted(
        (d.model_dump(mode="json", exclude={"policy_version", "inputs"}) for d in bundle.decisions),
        key=lambda d: d["clause_id"],
    )


def test_cli_and_api_static_audits_agree(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "build_target", lambda p: FakeChatTarget(vulnerable))
    monkeypatch.setattr(service, "build_target", lambda p: FakeChatTarget(vulnerable))

    res = CliRunner().invoke(
        cli.app,
        ["audit", "--profile", "examples/profiles/support_bot.yaml", "--out", str(tmp_path / "cli"),
         "--planner", "static", "--config", str(tmp_path / "none.toml"),
         "--as-of", "2026-11-14T10:00:00+00:00"],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    cli_dir = next((tmp_path / "cli").iterdir())

    (tmp_path / "api").mkdir()
    c = app_with(tmp_path / "api")
    rid = c.post(
        "/api/v1/runs",
        headers=H("r"),
        json={"profile_yaml": PROFILE, "planner": "static", "auto_approve": True},
    ).json()["run_id"]
    assert wait(c, rid) == "complete"
    api_dir = tmp_path / "api" / "runs" / rid

    assert verify_run(cli_dir).ok and verify_run(api_dir).ok
    cli_b, api_b = read_bundle(cli_dir), read_bundle(api_dir)
    assert _comparable(cli_b) == _comparable(api_b)
    assert cli_b.header.tier == api_b.header.tier and cli_b.status == api_b.status
