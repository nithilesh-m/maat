# ruff: noqa: E501
import tarfile

import pytest

from maat.evidence.verify import verify_run
from tests.test_runner import audit

pytestmark = pytest.mark.opa


def _sensitive_run(tmp_path):
    """A sealed run with one sensitive and one ordinary artifact."""
    from maat.evidence.artifacts import ArtifactStore
    from maat.evidence.bundle import build_bundle, write_bundle
    from maat.evidence.ledger import Ledger
    from maat.evidence.signing import RunKey
    from maat.schemas.evidence import EvidenceDraft
    from tests.fakes import AS_OF, SEED, seq_ids

    run = tmp_path / "run-s"
    run.mkdir()
    key = RunKey.from_seed(SEED)
    store = ArtifactStore(run / "artifacts", "run-s")
    secret = store.put_bytes(b"red-team transcript", "risk", "jailbreak.json", sensitive=True)
    plain = store.put_bytes(b"public outcome table", "risk", "outcomes.json")
    led = Ledger(run / "ledger.sqlite", "run-s", key, seq_ids())
    for ref in (secret, plain):
        led.append(
            EvidenceDraft(
                run_id="run-s",
                agent="risk",
                tool="probe_jailbreak@1.0.0",
                evidence_type="measured",
                target_ref="t",
                artifacts=[ref],
                started_at=AS_OF,
                ended_at=AS_OF,
            )
        )
    recs = led.records()
    led.close()
    b = build_bundle(
        run_id="run-s",
        target_ref="t",
        tier="limited",
        regimes=["EU"],
        versions={"catalog": "c"},
        created_at=AS_OF,
        records=recs,
        decisions=[],
        clause_ids_by_tool={},
    )
    write_bundle(b, run, key)
    return run, secret, plain


def test_sanitize_drops_sensitive_and_caches(tmp_path):
    from scripts.package_release import sanitize_run

    audit(tmp_path / "r", lambda m: "ok")
    (tmp_path / "r" / "llm_cache.sqlite").write_text("x")
    (tmp_path / "r" / "checkpoints.sqlite").write_text("x")
    out = sanitize_run(tmp_path / "r", tmp_path / "clean")
    assert not (out / "llm_cache.sqlite").exists() and not (out / "checkpoints.sqlite").exists()
    assert (out / "ledger.sqlite").exists() and (out / "bundle.dsse.json").exists()
    assert (out / "REDACTED_ARTIFACTS.txt").exists() and (out / "VERIFY_NOTE.md").exists()


def test_sensitive_artifacts_are_removed_and_listed_and_the_original_is_untouched(tmp_path):
    from scripts.package_release import sanitize_run

    run, secret, plain = _sensitive_run(tmp_path)
    out = sanitize_run(run, tmp_path / "clean")
    assert not (out / "artifacts" / secret.sha256.removeprefix("sha256:")).exists()
    assert (out / "artifacts" / plain.sha256.removeprefix("sha256:")).exists()
    assert (out / "REDACTED_ARTIFACTS.txt").read_text().split() == [secret.sha256]
    assert verify_run(run).ok  # the source run is unchanged


def test_verify_allow_redacted_skips_only_the_listed_artifacts(tmp_path):
    from scripts.package_release import sanitize_run

    run, secret, plain = _sensitive_run(tmp_path)
    out = sanitize_run(run, tmp_path / "clean")
    plain_report = verify_run(out)
    assert not plain_report.ok and any("artifact missing" in p for p in plain_report.problems)
    skip = set((out / "REDACTED_ARTIFACTS.txt").read_text().split())
    assert verify_run(out, skip_artifacts=skip).ok
    # tampering with an artifact that was NOT redacted is still caught
    (out / "artifacts" / plain.sha256.removeprefix("sha256:")).write_bytes(b"tampered")
    bad = verify_run(out, skip_artifacts=skip)
    assert not bad.ok and any("artifact altered" in p for p in bad.problems)


def test_cli_verify_allow_redacted(tmp_path):
    from typer.testing import CliRunner

    import maat.cli as cli
    from scripts.package_release import sanitize_run

    run, *_ = _sensitive_run(tmp_path)
    out = sanitize_run(run, tmp_path / "clean")
    r = CliRunner()
    assert r.invoke(cli.app, ["verify", str(out)]).exit_code == 1
    ok = r.invoke(
        cli.app, ["verify", str(out), "--allow-redacted", str(out / "REDACTED_ARTIFACTS.txt")]
    )
    assert ok.exit_code == 0 and "OK" in ok.output
    missing = r.invoke(
        cli.app, ["verify", str(out), "--allow-redacted", str(tmp_path / "nope.txt")]
    )
    assert missing.exit_code == 2


def test_package_release_builds_an_archive_without_caches_or_sensitive_files(tmp_path, monkeypatch):
    import subprocess

    from scripts import package_release as pr

    (tmp_path / "src").mkdir()
    run, secret, plain = _sensitive_run(tmp_path / "src")
    (run / "llm_cache.sqlite").write_text("cache")
    results = tmp_path / "work" / "experiments" / "results" / "final"
    results.mkdir(parents=True)
    (results / "rq1_by_condition.csv").write_text("condition\nmaat\n")
    monkeypatch.chdir(tmp_path / "work")
    (tmp_path / "work" / "docs").mkdir()
    (tmp_path / "work" / "docs" / "codebook.md").write_text("# codebook\n")
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=a@b",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
        check=True,
    )
    archive = pr.package_release(tmp_path / "dist", [tmp_path / "src"])
    with tarfile.open(archive) as t:
        names = t.getnames()
    joined = "\n".join(names)
    assert "code.tar" in joined and "experiments/results/final/rq1_by_condition.csv" in joined
    assert "runs/run-s/ledger.sqlite" in joined and "llm_cache.sqlite" not in joined
    assert secret.sha256.removeprefix("sha256:") not in joined
    assert plain.sha256.removeprefix("sha256:") in joined


def _with_child(tmp_path):
    """A sealed parent run plus a remediation child that has its own sensitive artifact."""
    import shutil

    (tmp_path / "src").mkdir()
    run, secret, plain = _sensitive_run(tmp_path / "src")
    child_parent = tmp_path / "child-src"
    child_parent.mkdir()
    child, child_secret, _ = _sensitive_run(child_parent)
    (run / "children").mkdir()
    shutil.copytree(child, run / "children" / "run-s-child-1")
    (run / "children" / "run-s-child-1" / "llm_cache.sqlite").write_text("cache")
    return run, secret, child_secret


def test_c1_children_are_sanitized_too(tmp_path):
    from scripts.package_release import sanitize_run

    run, secret, child_secret = _with_child(tmp_path)
    out = sanitize_run(run, tmp_path / "clean")
    child = out / "children" / "run-s-child-1"
    assert not (child / "artifacts" / child_secret.sha256.removeprefix("sha256:")).exists()
    assert not (child / "llm_cache.sqlite").exists()
    assert (child / "REDACTED_ARTIFACTS.txt").read_text().split() == [child_secret.sha256]
    skip = set((child / "REDACTED_ARTIFACTS.txt").read_text().split())
    assert verify_run(child, skip_artifacts=skip).ok


def test_cache_journal_and_wal_files_are_dropped(tmp_path):
    from scripts.package_release import sanitize_run

    run, *_ = _sensitive_run(tmp_path)
    for name in ("llm_cache.sqlite-journal", "tool_cache.sqlite-wal", "checkpoints.sqlite-shm"):
        (run / name).write_text("x")
    out = sanitize_run(run, tmp_path / "clean")
    assert not [p for p in out.iterdir() if "cache" in p.name or "checkpoints" in p.name]


def test_c2_release_refuses_run_like_folders_in_the_results(tmp_path, monkeypatch):
    import subprocess

    from scripts import package_release as pr

    work = tmp_path / "work"
    final = work / "experiments" / "results" / "final"
    (final / "replays" / "x").mkdir(parents=True)
    (final / "replays" / "x" / "llm_cache.sqlite").write_text("cache")
    (final / "rq1.csv").write_text("a\n1\n")
    monkeypatch.chdir(work)
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=a@b",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
        check=True,
    )
    with pytest.raises(ValueError, match="sqlite"):
        pr.package_release(tmp_path / "dist", [])


def test_i3_allow_redacted_cannot_hide_tampering_of_a_non_sensitive_artifact(tmp_path):
    from scripts.package_release import sanitize_run

    run, secret, plain = _sensitive_run(tmp_path)
    out = sanitize_run(run, tmp_path / "clean")
    plain_file = out / "artifacts" / plain.sha256.removeprefix("sha256:")
    plain_file.write_bytes(b"tampered")
    skip = set((out / "REDACTED_ARTIFACTS.txt").read_text().split()) | {
        plain.sha256
    }  # attacker adds it
    rep = verify_run(out, skip_artifacts=skip)
    assert not rep.ok and any("artifact altered" in p for p in rep.problems)
    plain_file.unlink()
    rep = verify_run(out, skip_artifacts=skip)
    assert not rep.ok and any("artifact missing" in p for p in rep.problems)


def test_i3_a_present_sensitive_artifact_is_still_hash_checked_and_skips_are_reported(tmp_path):
    from typer.testing import CliRunner

    import maat.cli as cli
    from scripts.package_release import sanitize_run

    run, secret, plain = _sensitive_run(tmp_path)
    (run / "artifacts" / secret.sha256.removeprefix("sha256:")).write_bytes(b"altered")
    rep = verify_run(run, skip_artifacts={secret.sha256})
    assert not rep.ok and any("artifact altered" in p for p in rep.problems)
    run2, *_ = (
        _sensitive_run(tmp_path / "again") if (tmp_path / "again").mkdir() is None else (None,)
    )
    out = sanitize_run(run2, tmp_path / "clean")
    ok = CliRunner().invoke(
        cli.app, ["verify", str(out), "--allow-redacted", str(out / "REDACTED_ARTIFACTS.txt")]
    )
    assert ok.exit_code == 0 and "1 artifact" in ok.output and "redacted" in ok.output
