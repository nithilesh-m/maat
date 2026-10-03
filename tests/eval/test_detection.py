# ruff: noqa: E501
import pandas as pd
import pytest

from maat.eval.detection import Defect, bootstrap_ci, detection_scores, load_defects


def test_final_guard(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(
        "- {id: D1, testbed: t1, variant: seeded, split: test, description: x, controls: [VG-SEC-01]}\n"
    )
    with pytest.raises(ValueError, match="--final"):
        load_defects(p, "test")
    with pytest.raises(ValueError, match="--final"):
        load_defects(p, "all")
    assert load_defects(p, "test", final=True)[0].id == "D1"
    assert load_defects(p, "dev") == []  # dev never needs the flag


def _d(i, ctrl, split="dev"):
    return Defect(
        id=i, testbed="t1", variant="seeded", split=split, description="", controls=[ctrl]
    )


def test_scores():
    defects = [_d("D1", "VG-SEC-01"), _d("D2", "VG-PRIV-01")]
    flagged = {"t1_seeded__maat__r0": {"VG-SEC-01"}, "t1_clean__maat__r0": {"VG-PRIV-01"}}
    idx = pd.DataFrame(
        [
            {"cell_id": k, "condition": "maat", "repeat": 0, "status": "complete", "run_dir": k}
            for k in flagged
        ]
    )
    df = detection_scores(idx, defects, flagged_of=lambda run_dir: flagged[run_dir])
    row = df.iloc[0]
    assert (row.tp, row.fn, row.fp) == (1, 1, 1) and row.precision == 0.5 and row.recall == 0.5
    assert row.caught == "D1"


def test_failed_cells_are_excluded_and_conditions_are_kept_apart():
    defects = [_d("D1", "VG-SEC-01")]
    flagged = {"t1_seeded__maat__r0": {"VG-SEC-01"}, "t1_seeded__b0__r0": set()}
    idx = pd.DataFrame(
        [
            {"cell_id": "t1_seeded__maat__r0", "condition": "maat", "repeat": 0, "status": "complete", "run_dir": "t1_seeded__maat__r0"},
            {"cell_id": "t1_seeded__b0__r0", "condition": "b0", "repeat": 0, "status": "complete", "run_dir": "t1_seeded__b0__r0"},
            {"cell_id": "t1_seeded__a1__r0", "condition": "a1", "repeat": 0, "status": "failed", "run_dir": None},
        ]
    )  # fmt: skip
    df = detection_scores(idx, defects, flagged_of=lambda rd: flagged[rd]).set_index("condition")
    assert set(df.index) == {"maat", "b0"}  # the failed a1 cell does not appear
    assert df.loc["maat", "recall"] == 1.0 and df.loc["b0", "recall"] == 0.0
    assert df.loc["maat", "fp"] == 0  # no clean run recorded: nothing to count as a false positive


def test_bootstrap_ci_brackets_the_mean_and_is_deterministic():
    vals = [0.2, 0.4, 0.6, 0.8, 1.0]
    lo, hi = bootstrap_ci(vals, n=500, seed=1)
    assert lo <= 0.6 <= hi and (lo, hi) == bootstrap_ci(vals, n=500, seed=1)
    assert all(v != v for v in bootstrap_ci([]))  # NaNs for no data


@pytest.mark.opa
def test_flagged_controls_reads_decisions_and_undisputed_findings(tmp_path):
    from maat.eval.detection import flagged_controls
    from tests.fakes import vulnerable
    from tests.test_runner import audit

    audit(tmp_path / "r", vulnerable)
    flagged = flagged_controls(str(tmp_path / "r"))
    assert "VG-SEC-01" in flagged and "VG-FAIR-04" not in flagged


def test_i5_missing_clean_twin_gives_nan_precision_not_a_perfect_score():
    defects = [_d("D1", "VG-SEC-01")]
    idx = pd.DataFrame(
        [
            {"cell_id": "t1_seeded__b2__r0", "condition": "b2", "repeat": 0, "status": "complete", "run_dir": "s"},
            {"cell_id": "t1_clean__b2__r0", "condition": "b2", "repeat": 0, "status": "failed", "run_dir": None},
        ]
    )  # fmt: skip
    row = detection_scores(idx, defects, flagged_of=lambda rd: {"VG-SEC-01"}).iloc[0]
    assert row.recall == 1.0 and pd.isna(row.precision) and row.clean_missing
