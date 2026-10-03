import pytest
from typer.testing import CliRunner

import maat.cli as cli
from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from tests.fakes import vulnerable
from tests.test_runner import audit

pytestmark = pytest.mark.opa
runner = CliRunner()


def test_review_list_and_decide(tmp_path):
    audit(tmp_path / "r", vulnerable)
    key = tmp_path / "rev.pem"
    res = runner.invoke(cli.app, ["review", "list", str(tmp_path / "r")])
    assert res.exit_code == 0 and "RG-OVS-01" in res.output
    res = runner.invoke(
        cli.app,
        ["review", "decide", str(tmp_path / "r"), "RG-OVS-01", "--label", "N",
         "--reviewer", "a.reviewer", "--rationale", "no oversight doc", "--key", str(key)],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    assert key.exists() and "generated" in res.output  # key created on first use, with notice
    assert "RG-OVS-01" not in runner.invoke(cli.app, ["review", "list", str(tmp_path / "r")]).output
    assert verify_run(tmp_path / "r").ok


def test_waiver_add_via_cli(tmp_path):
    audit(tmp_path / "r", vulnerable)
    key = tmp_path / "rev.pem"
    RunKey.generate().save_pem(key)
    res = runner.invoke(
        cli.app,
        ["waiver", "add", str(tmp_path / "r"), "--control", "VG-SEC-01", "--owner", "DPO",
         "--scope", "dev", "--expiry", "2030-01-01T00:00:00+00:00",
         "--compensation", "assistive mode", "--key", str(key)],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "waive" in res.output
    assert verify_run(tmp_path / "r").ok


def test_review_decide_bad_label_is_usage_error(tmp_path):
    audit(tmp_path / "r", vulnerable)
    res = runner.invoke(
        cli.app,
        ["review", "decide", str(tmp_path / "r"), "RG-OVS-01", "--label", "Z",
         "--reviewer", "x", "--rationale", "y", "--key", str(tmp_path / "k.pem")],
    )  # fmt: skip
    assert res.exit_code == 2 and "label" in res.output


def test_review_on_tampered_run_fails_cleanly(tmp_path):
    audit(tmp_path / "r", vulnerable)
    (tmp_path / "r" / "bundle.dsse.json").write_text("{}")
    res = runner.invoke(cli.app, ["review", "list", str(tmp_path / "r")])
    assert res.exit_code == 2 and "Traceback" not in res.output
