# ruff: noqa: E501
import pandas as pd
import pytest

from experiments.freeze import check, write_manifest
from experiments.plots import bar_with_ci, box, slope, stacked_outcomes


def test_freeze_roundtrip(tmp_path):
    (tmp_path / "a.csv").write_text("x\n1\n")
    write_manifest(tmp_path)
    assert check(tmp_path) == []
    (tmp_path / "a.csv").write_text("x\n2\n")
    assert check(tmp_path) == ["a.csv"]


def test_freeze_detects_missing_and_extra_files_and_sorts_the_manifest(tmp_path):
    (tmp_path / "b.csv").write_text("1")
    (tmp_path / "a.csv").write_text("2")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.csv").write_text("3")
    write_manifest(tmp_path)
    lines = (tmp_path / "MANIFEST.sha256").read_text().splitlines()
    assert [ln.split("  ", 1)[1] for ln in lines] == ["a.csv", "b.csv", "sub/c.csv"]
    (tmp_path / "b.csv").unlink()
    (tmp_path / "new.csv").write_text("4")
    assert check(tmp_path) == ["b.csv", "new.csv"]


def test_freeze_cli_check_exits_nonzero_on_mismatch(tmp_path):
    import subprocess
    import sys

    (tmp_path / "a.csv").write_text("1")
    write_manifest(tmp_path)
    ok = subprocess.run(
        [sys.executable, "-m", "experiments.freeze", "--dir", str(tmp_path), "--check"],
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0 and "OK" in ok.stdout
    (tmp_path / "a.csv").write_text("2")
    bad = subprocess.run(
        [sys.executable, "-m", "experiments.freeze", "--dir", str(tmp_path), "--check"],
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 1 and "a.csv" in bad.stdout


def test_plot_writes_files(tmp_path):
    df = pd.DataFrame(
        {"condition": ["maat", "b0"], "f1": [0.8, 0.5], "lo": [0.7, 0.4], "hi": [0.9, 0.6]}
    )
    bar_with_ci(df, "condition", "f1", "lo", "hi", tmp_path / "f1")
    assert (tmp_path / "f1.png").exists() and (tmp_path / "f1.svg").exists()


def test_other_plots_write_png_and_svg(tmp_path):
    stacked_outcomes(
        pd.DataFrame(
            {"group": ["rego", "judge_panel"], "flipped": [0.0, 0.2], "abstained": [0.1, 0.3]}
        ),
        tmp_path / "s",
    )
    slope(
        pd.DataFrame({"control_id": ["VG-SEC-01"], "metric_before": [1.0], "metric_after": [0.0]}),
        tmp_path / "sl",
    )
    box(
        pd.DataFrame({"condition": ["a", "a", "b"], "gpu_hours_est": [1.0, 2.0, 3.0]}),
        "condition",
        "gpu_hours_est",
        tmp_path / "bx",
    )
    for stem in ("s", "sl", "bx"):
        assert (tmp_path / f"{stem}.png").stat().st_size > 0 and (
            tmp_path / f"{stem}.svg"
        ).stat().st_size > 0


@pytest.mark.opa
def test_analyze_all_builds_the_frozen_results_and_reports_failed_cells(tmp_path):
    from experiments.analyze_all import analyze_all
    from tests.fakes import robust, vulnerable
    from tests.test_runner import audit

    results = tmp_path / "results"
    (results / "rq1").mkdir(parents=True)
    audit(results / "rq1" / "seeded", vulnerable)
    audit(results / "rq1" / "clean", robust)
    pd.DataFrame(
        [
            {
                "cell_id": "t1_seeded__maat__r0",
                "condition": "maat",
                "repeat": 0,
                "status": "complete",
                "run_dir": str(results / "rq1" / "seeded"),
                "error": None,
            },
            {
                "cell_id": "t1_clean__maat__r0",
                "condition": "maat",
                "repeat": 0,
                "status": "complete",
                "run_dir": str(results / "rq1" / "clean"),
                "error": None,
            },
            {
                "cell_id": "t1_seeded__b2__r0",
                "condition": "b2",
                "repeat": 0,
                "status": "failed",
                "run_dir": None,
                "error": "RuntimeError: ollama OOM",
            },
        ]
    ).to_csv(results / "rq1" / "index.csv", index=False)
    defects = tmp_path / "defects.yaml"
    defects.write_text(
        "- {id: D1, testbed: t1, variant: seeded, split: dev, description: x, controls: [VG-SEC-01]}\n"
    )
    final = tmp_path / "final"
    analyze_all(results, final, defects=defects, split="dev", final_flag=False)
    assert (final / "rq1_by_condition.csv").exists() and (final / "tables.md").exists()
    assert (final / "figures" / "rq1_f1.png").exists()
    failed = pd.read_csv(final / "failed_cells.csv")
    assert list(failed.cell_id) == ["t1_seeded__b2__r0"] and "OOM" in failed.error.iloc[0]
    assert "rq1_by_condition.csv" in (final / "tables.md").read_text()  # each row names its source
    assert check(final) == []


def test_b3_manual_baseline_is_scored_with_the_same_detection_logic(tmp_path):
    from experiments.analyze_b3 import analyze_b3

    sheet = tmp_path / "sheet.csv"
    sheet.write_text(
        "auditor,system,control_id,label,evidence,minutes\n"
        "A,t1_seeded,VG-SEC-01,N,tried injection by hand,12\n"
        "A,t1_seeded,VG-PRIV-01,S,asked for emails,8\n"
        "B,t1_seeded,VG-SEC-01,P,partial,10\n"
        "B,t1_seeded,VG-PRIV-01,N,leak,7\n"
    )
    defects = tmp_path / "d.yaml"
    defects.write_text(
        "- {id: D1, testbed: t1, variant: seeded, split: dev, description: x, controls: [VG-SEC-01]}\n"
        "- {id: D2, testbed: t1, variant: seeded, split: dev, description: y, controls: [VG-PRIV-01]}\n"
    )
    df = analyze_b3(sheet, defects, split="dev")
    assert set(df.condition) == {"b3"} and len(df) == 2  # one row per auditor
    a = df[df.repeat == 0].iloc[0]  # auditor A flagged only D1 (N), not D2 (S)
    assert (a.tp, a.fn) == (1, 1)
    b = df[df.repeat == 1].iloc[0]  # auditor B flagged both (P and N count as flagged)
    assert (b.tp, b.fn) == (2, 0)


def test_b3_guards_the_test_split_like_every_other_analysis(tmp_path):
    from experiments.analyze_b3 import analyze_b3

    sheet = tmp_path / "s.csv"
    sheet.write_text(
        "auditor,system,control_id,label,evidence,minutes\nA,t1_seeded,VG-SEC-01,N,x,1\n"
    )
    defects = tmp_path / "d.yaml"
    defects.write_text(
        "- {id: D1, testbed: t1, variant: seeded, split: test, description: x, controls: [VG-SEC-01]}\n"
    )
    with pytest.raises(ValueError, match="--final"):
        analyze_b3(sheet, defects, split="test")


def test_i7_a_failing_rq_does_not_abort_the_analysis_and_is_reported(tmp_path, monkeypatch):
    import experiments.run_rq3 as rq3
    from experiments.analyze_all import analyze_all

    results = tmp_path / "results"
    (results / "rq3").mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "cell_id": "t1_seeded__maat__r0",
                "condition": "maat",
                "status": "complete",
                "run_dir": "x",
                "system": "y",
            }
        ]
    ).to_csv(results / "rq3" / "index.csv", index=False)
    monkeypatch.setattr(
        rq3, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("target down"))
    )
    final = tmp_path / "final"
    analyze_all(results, final)
    errs = pd.read_csv(final / "analysis_errors.csv")
    assert errs.rq.tolist() == ["rq3"] and "target down" in errs.error.iloc[0]
    assert (final / "MANIFEST.sha256").exists() and (final / "tables.md").exists()


def test_i7_analysis_reuses_existing_remediation_results_instead_of_re_running(
    tmp_path, monkeypatch
):
    import experiments.run_rq3 as rq3
    from experiments.analyze_all import analyze_all

    results = tmp_path / "results"
    (results / "rq3").mkdir(parents=True)
    pd.DataFrame(
        [{"cell_id": "c", "condition": "maat", "status": "complete", "run_dir": "x", "system": "y"}]
    ).to_csv(results / "rq3" / "index.csv", index=False)
    for n in ("rq3_controls.csv", "rq3_utility.csv", "rq3_summary.csv"):
        pd.DataFrame([{"testbed": "t1", "v": 1}]).to_csv(results / "rq3" / n, index=False)
    monkeypatch.setattr(
        rq3, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not re-run"))
    )
    final = tmp_path / "final"
    analyze_all(results, final)
    assert (final / "rq3_summary.csv").exists()
    assert (
        not (final / "analysis_errors.csv").exists()
        or pd.read_csv(final / "analysis_errors.csv").empty
    )


def test_c2_replay_check_leaves_nothing_behind_in_the_results_folder(tmp_path):
    from experiments.run_rq4 import run as run4

    results = tmp_path / "res"
    results.mkdir()
    pd.DataFrame(
        [{"cell_id": "t1_seeded__b0__r0", "condition": "b0", "status": "failed", "run_dir": None}]
    ).to_csv(results / "index.csv", index=False)
    out = tmp_path / "final"
    run4(results / "index.csv", out, trials=2)
    assert not (out / "replays").exists()
    assert not list(out.rglob("*.sqlite"))
