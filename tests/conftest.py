import os
import shutil

import pytest


def pytest_collection_modifyitems(config, items):
    skip_opa = pytest.mark.skip(reason="opa binary not on PATH (brew install opa)")
    skip_ollama = pytest.mark.skip(reason="set MAAT_OLLAMA_TESTS=1 with Ollama running")
    have_opa = shutil.which("opa") is not None
    want_ollama = os.environ.get("MAAT_OLLAMA_TESTS") == "1"
    for item in items:
        if "opa" in item.keywords and not have_opa:
            item.add_marker(skip_opa)
        if "ollama" in item.keywords and not want_ollama:
            item.add_marker(skip_ollama)


@pytest.fixture(autouse=True)
def _no_dataset_downloads(monkeypatch):
    """Unit tests must never hit the network for JailbreakBench behaviours."""
    import maat.tools.risk.jailbreak as jb

    monkeypatch.setattr(jb, "load_behaviors", lambda split: ["synthetic harmful goal"])
