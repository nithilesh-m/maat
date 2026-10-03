from pathlib import Path

import pytest
import yaml

from maat.profile.loader import load_profile
from maat.targets.factory import build_target
from testbed.rag_bot.config import load_bot_config

NAMES = ["t1_clean", "t1_seeded", "t2_clean", "t2_seeded"]


@pytest.mark.parametrize("name", NAMES)
def test_profile_builds_in_process_target(name):
    prof = load_profile(Path(f"examples/profiles/{name}.yaml"))
    target = build_target(prof)
    assert target.version_hash.startswith("sha256:")


def test_clean_is_hardened_and_seeded_is_not():
    clean = load_bot_config(Path("testbed/rag_bot/variants/t1_clean.yaml"))
    seeded = load_bot_config(Path("testbed/rag_bot/variants/t1_seeded.yaml"))
    assert clean.hardened and clean.disclose_ai and clean.require_citations
    assert not seeded.hardened and not seeded.disclose_ai and seeded.tone_instruction
    assert "corpus_seeded" in " ".join(seeded.corpus_dirs)


def test_seeded_profiles_have_missing_documentation_defect():
    for name in ("t1_seeded", "t2_seeded"):
        raw = yaml.safe_load(Path(f"examples/profiles/{name}.yaml").read_text())
        assert raw["artifacts"]["docs"] == [] and "logs" not in raw["artifacts"]


def test_qa_set_has_twelve_items():
    qa = yaml.safe_load(Path("testbed/rag_bot/qa_set.yaml").read_text())["items"]
    assert len(qa) == 12
