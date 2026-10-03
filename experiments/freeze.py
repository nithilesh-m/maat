"""Freeze a results directory with a SHA-256 manifest, or check it.

uv run python -m experiments.freeze --dir experiments/results/final          # write
uv run python -m experiments.freeze --dir experiments/results/final --check  # verify
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

MANIFEST = "MANIFEST.sha256"


def _files(d: Path) -> list[Path]:
    return sorted(p for p in d.rglob("*") if p.is_file() and p.name != MANIFEST)


def write_manifest(d: Path) -> None:
    lines = [
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(d).as_posix()}"
        for p in _files(d)
    ]
    (d / MANIFEST).write_text("\n".join(lines) + "\n")


def check(d: Path) -> list[str]:
    """Paths that were changed, removed or added since the manifest was written."""
    expected = {}
    for line in (d / MANIFEST).read_text().splitlines():
        if line:
            h, rel = line.split("  ", 1)
            expected[rel] = h
    bad = [
        rel
        for rel, h in expected.items()
        if not (d / rel).exists() or hashlib.sha256((d / rel).read_bytes()).hexdigest() != h
    ]
    extra = [
        p.relative_to(d).as_posix()
        for p in _files(d)
        if p.relative_to(d).as_posix() not in expected
    ]
    return sorted(bad + extra)


if __name__ == "__main__":
    d = Path(sys.argv[sys.argv.index("--dir") + 1])
    if "--check" in sys.argv:
        problems = check(d)
        print("\n".join(problems) or "OK")
        sys.exit(1 if problems else 0)
    write_manifest(d)
