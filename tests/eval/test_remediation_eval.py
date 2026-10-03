# ruff: noqa: E501
import pytest

from maat.eval.remediation_eval import assert_heldout
from maat.schemas.evidence import EvidenceRecord
from tests.fakes import AS_OF


def rec(split, tool="probe_prompt_injection@1.0.0", params=None):
    return EvidenceRecord(
        run_id="c", agent="risk", tool=tool, evidence_type="measured", target_ref="t",
        params=params if params is not None else {"split": split}, result={"metrics": {"asr": 0}},
        started_at=AS_OF, ended_at=AS_OF, id="r", seq=0, prev_hash="p", signer="k", hash="h", sig="s",
    )  # fmt: skip


def test_heldout_guard():
    assert_heldout([rec("heldout")])
    with pytest.raises(ValueError, match="held-out"):
        assert_heldout([rec("dev")])


def test_non_probe_tools_are_exempt_and_missing_split_is_rejected():
    assert_heldout([rec("dev", tool="task_utility@1.0.0")])
    with pytest.raises(ValueError, match="held-out"):
        assert_heldout([rec("", params={})])


@pytest.mark.opa
def test_rows_and_utility_from_a_real_remediation(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    import maat.cli as cli
    import maat.service as service
    from maat.catalog.loader import load_catalog
    from maat.eval.remediation_eval import remediation_rows, utility_rows
    from maat.profile.loader import load_profile
    from maat.targets.testbed import TestbedTarget
    from testbed.rag_bot.config import BotConfig
    from tests.remediation.test_remediate_e2e import PROFILE, gullible

    build = lambda p: TestbedTarget(BotConfig(), upstream=gullible, model_family="mistral")  # noqa: E731
    monkeypatch.setattr(cli, "build_target", build)
    monkeypatch.setattr(service, "build_target", build)
    prof_path = tmp_path / "p.yaml"
    prof_path.write_text(PROFILE % "true")
    res = CliRunner().invoke(
        cli.app,
        ["audit", "--profile", str(prof_path), "--out", str(tmp_path / "runs"), "--planner", "static",
         "--config", str(tmp_path / "none.toml")],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    parent = next((tmp_path / "runs").iterdir())
    result = service.remediate_run(
        parent, load_profile(prof_path), apply=True, target_builder=build, regime="EU"
    )
    child = result.child_dir
    rows = remediation_rows(parent, child, load_catalog())
    sec = next(r for r in rows if r["control_id"] == "VG-SEC-01" and r["regime"] == "EU")
    assert (sec["before_outcome"], sec["after_outcome"]) == ("block", "pass")
    assert sec["metric"] == "asr" and sec["metric_before"] == 1.0 and sec["metric_after"] == 0.0
    assert sec["split_after"] == "heldout"
    util = utility_rows(child)
    assert util["utility_metric"] == "qa_accuracy" and util["delta"] is not None


@pytest.mark.opa
def test_run_rq3_writes_the_three_csvs(tmp_path, monkeypatch):
    import pandas as pd
    from typer.testing import CliRunner

    import maat.cli as cli
    import maat.service as service
    from experiments.run_rq3 import run
    from maat.targets.testbed import TestbedTarget
    from testbed.rag_bot.config import BotConfig
    from tests.remediation.test_remediate_e2e import PROFILE, gullible

    build = lambda p: TestbedTarget(BotConfig(), upstream=gullible, model_family="mistral")  # noqa: E731
    monkeypatch.setattr(cli, "build_target", build)
    monkeypatch.setattr(service, "build_target", build)
    prof = tmp_path / "t1_seeded.yaml"
    prof.write_text(PROFILE % "false")
    res = CliRunner().invoke(
        cli.app,
        ["audit", "--profile", str(prof), "--out", str(tmp_path / "runs"), "--planner", "static",
         "--config", str(tmp_path / "none.toml")],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    parent = next((tmp_path / "runs").iterdir())
    idx = tmp_path / "index.csv"
    pd.DataFrame(
        [
            {
                "cell_id": "t1_seeded__maat__r0",
                "system": str(prof),
                "status": "complete",
                "run_dir": str(parent),
            }
        ]
    ).to_csv(idx, index=False)
    summary = run(idx, tmp_path / "out", target_builder=build)
    assert summary.iloc[0].testbed == "t1" and summary.iloc[0].share_flipped_to_pass > 0
    ctl = pd.read_csv(tmp_path / "out" / "rq3_controls.csv")
    assert (
        ctl.sandbox_override.all() and (ctl.split_after == "heldout").all()
    )  # recorded, not hidden
    for f in ("rq3_utility.csv", "rq3_summary.csv"):
        assert (tmp_path / "out" / f).exists()
