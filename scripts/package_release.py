"""Build the public artifact. Excludes LLM/tool caches, checkpoints and all sensitive artifacts.

    uv run python scripts/package_release.py --out dist --runs experiments/results/rq1/runs

Run it from a clean checkout of the release tag: the code is exported with `git archive HEAD`.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import tarfile
from pathlib import Path

from maat import __version__
from maat.schemas.evidence import EvidenceRecord

# Caches can hold red-team content; match journal/wal/shm side files too.
DROP = ("llm_cache.sqlite*", "tool_cache.sqlite*", "checkpoints.sqlite*", ".maat.lock")


def sensitive_hashes(run: Path) -> set[str]:
    c = sqlite3.connect(f"file:{run / 'ledger.sqlite'}?mode=ro", uri=True)
    try:
        recs = [
            EvidenceRecord.model_validate_json(b) for (b,) in c.execute("SELECT body FROM evidence")
        ]
    finally:
        c.close()
    return {a.sha256.removeprefix("sha256:") for r in recs for a in r.artifacts if a.sensitive}


def _sanitize_one(src: Path, dst: Path) -> None:
    dropped = sorted(h for h in sensitive_hashes(src) if (dst / "artifacts" / h).exists())
    for h in dropped:
        (dst / "artifacts" / h).unlink()
    (dst / "REDACTED_ARTIFACTS.txt").write_text("".join(f"sha256:{h}\n" for h in dropped))
    (dst / "VERIFY_NOTE.md").write_text(
        "Sensitive artifacts were removed for publication. Run `maat verify --allow-redacted "
        "REDACTED_ARTIFACTS.txt <dir>`; the hash chain, signatures and bundle checks still apply, "
        "and every artifact that was not redacted is still checked.\n"
    )


def sanitize_run(run: Path, out_root: Path) -> Path:
    """Copy a run without caches and sensitive artifacts. Child runs (remediation re-tests live in
    `children/`) are separate ledgers with their own sensitive artifacts, so every directory that
    holds a ledger is sanitized, each with its own redaction list."""
    out = Path(out_root) / run.name
    shutil.copytree(run, out, ignore=shutil.ignore_patterns(*DROP))
    _sanitize_one(run, out)
    for ledger in sorted(run.rglob("ledger.sqlite")):
        src = ledger.parent
        if src != run:
            _sanitize_one(src, out / src.relative_to(run))
    return out


def _refuse_run_like_files(root: Path) -> None:
    """The frozen results hold CSVs and figures only; a stray run folder would ship caches."""
    bad = [p for p in root.rglob("*.sqlite*") if p.name != "ledger.sqlite"] + list(
        root.rglob("ledger.sqlite")
    )
    if bad:
        raise ValueError(
            f"refusing to package sqlite files under {root}: {sorted(map(str, bad))[:3]}"
        )


def package_release(out: Path, runs_dirs: list[Path], include_runs: bool = True) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    stage = out / f"maat-release-{__version__}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    subprocess.run(
        ["git", "archive", "--format=tar", "-o", str(stage / "code.tar"), "HEAD"], check=True
    )
    for p in ["docs/codebook.md", "annotations/gold.jsonl", "experiments/results/final"]:
        src = Path(p)
        if src.is_dir():
            _refuse_run_like_files(src)
            shutil.copytree(src, stage / p)
        elif src.exists():
            (stage / p).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, stage / p)
    if include_runs:
        for rd in runs_dirs:
            for bundle in sorted(Path(rd).glob("*/bundle.dsse.json")):
                sanitize_run(bundle.parent, stage / "runs")
    archive = out / f"maat-release-{__version__}.tar.gz"
    with tarfile.open(archive, "w:gz") as t:
        t.add(stage, arcname=stage.name)
    return archive


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("dist"))
    ap.add_argument("--runs", type=Path, nargs="*", default=[])
    a = ap.parse_args()
    print(package_release(a.out, a.runs))
