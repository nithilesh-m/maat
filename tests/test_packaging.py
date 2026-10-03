import subprocess
import sys


def test_testbed_adapter_importable_outside_repo_root(tmp_path):
    """The installed `maat` entry point must work from any directory (no reliance on cwd)."""
    proc = subprocess.run(
        [sys.executable, "-c", "import maat.targets.testbed, maat.cli"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
