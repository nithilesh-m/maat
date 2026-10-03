import pandas as pd

from maat.eval.matrix import MatrixConfig, cells, run_matrix

CFG = MatrixConfig.model_validate(
    {
        "name": "t",
        "systems": ["a.yaml", "b.yaml"],
        "repeats": 2,
        "llm_mode": "live",
        "conditions": [
            {"name": "maat", "options": {"planner": "agents"}},
            {"name": "b0", "options": {"planner": "static"}},
        ],
    }
)


def test_cells_deterministic():
    ids = [c.cell_id for c in cells(CFG)]
    assert len(ids) == 8 and ids == [c.cell_id for c in cells(CFG)] and ids[0] == "a__maat__r0"


def test_failures_recorded_and_resume(tmp_path):
    calls = []

    def ex(cell, out):
        calls.append(cell.cell_id)
        if cell.condition == "b0":
            raise RuntimeError("ollama OOM")
        return {"run_id": cell.cell_id, "run_dir": str(out / cell.cell_id), "bundle_id": "sha256:x"}

    df = run_matrix(CFG, tmp_path, executor=ex)
    assert (df.status == "failed").sum() == 4 and (df.status == "complete").sum() == 4
    assert df[df.status == "failed"].error.str.contains("OOM").all()
    assert len(list((tmp_path / "errors").glob("*.txt"))) == 4  # tracebacks kept for diagnosis
    calls.clear()
    run_matrix(CFG, tmp_path, executor=ex)
    assert all("b0" in c for c in calls) and len(calls) == 4  # only failed cells re-attempted


def test_one_failing_cell_does_not_stop_the_others(tmp_path):
    def ex(cell, out):
        if cell.cell_id == "a__maat__r0":
            raise RuntimeError("target down")
        return {"run_id": cell.cell_id, "run_dir": "x", "bundle_id": "b"}

    df = run_matrix(CFG, tmp_path, executor=ex)
    assert len(df) == 8 and (df.status == "complete").sum() == 7  # Review Focus #4


def test_index_records_provenance_columns(tmp_path):
    df = run_matrix(
        CFG, tmp_path, executor=lambda c, o: {"run_id": c.cell_id, "run_dir": "x", "bundle_id": "b"}
    )
    for col in ("config_hash", "model_digests", "started", "ended", "status", "error", "bundle_id"):
        assert col in df.columns
    assert df.config_hash.nunique() == 1 and len(df.config_hash.iloc[0]) == 16
    assert pd.read_csv(tmp_path / "index.csv").shape[0] == 8


def test_config_hash_changes_with_config():
    other = CFG.model_copy(update={"repeats": 3})
    assert CFG.hash() != other.hash()


def test_i4_a_cell_that_failed_after_its_run_dir_was_created_can_be_retried(tmp_path):
    attempts = {"n": 0}

    def ex(cell, out):
        run_dir = out / "runs" / f"{CFG.name}-{cell.cell_id}"
        if cell.cell_id == "a__maat__r0":
            attempts["n"] += 1
            if run_dir.exists():
                raise RuntimeError("run directory already exists")  # what open_run would do
            run_dir.mkdir(parents=True)
            if attempts["n"] == 1:
                raise RuntimeError("target down")  # fails AFTER the run dir exists
        return {"run_id": cell.cell_id, "run_dir": str(run_dir), "bundle_id": "b"}

    df = run_matrix(CFG, tmp_path, executor=ex)
    assert df[df.cell_id == "a__maat__r0"].status.iloc[0] == "failed"
    df = run_matrix(CFG, tmp_path, executor=ex)
    assert (df.status == "complete").all()  # the retry succeeded
    assert (
        len(list((tmp_path / "failed").iterdir())) == 1
    )  # the failed attempt was kept for diagnosis


def test_i4_resume_refuses_to_mix_configurations(tmp_path):
    import pytest

    ok = lambda c, o: {"run_id": c.cell_id, "run_dir": "x", "bundle_id": "b"}  # noqa: E731
    run_matrix(CFG, tmp_path, executor=ok)
    changed = CFG.model_copy(update={"repeats": 3})
    with pytest.raises(ValueError, match="config"):
        run_matrix(changed, tmp_path, executor=ok)
