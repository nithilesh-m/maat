from pathlib import Path

import pytest

from maat.profile.loader import ProfileError, load_profile
from maat.schemas.profile import TIER_LEVEL, RiskTier, SystemProfile, SystemType

VALID = """
profile_version: 1
name: support-bot
system_type: rag
description: Answers billing questions
intended_use: customer billing support
declared_risk_tier: limited
target:
  adapter: chat
  endpoint: http://localhost:8000/v1
  model: testbed
  model_family: mistral
"""


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "profile.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_valid_profile_loads_with_defaults(tmp_path):
    prof = load_profile(write(tmp_path, VALID))
    assert isinstance(prof, SystemProfile)
    assert prof.system_type is SystemType.RAG
    assert prof.declared_risk_tier is RiskTier.LIMITED
    assert prof.data_egress == "local_only"
    assert prof.sandbox_allowed is False
    assert prof.artifacts.docs == []


def test_tier_levels():
    assert TIER_LEVEL == {RiskTier.MINIMAL: 1, RiskTier.LIMITED: 2, RiskTier.HIGH: 3}


def test_unknown_field_rejected(tmp_path):
    with pytest.raises(ProfileError, match="extra"):
        load_profile(write(tmp_path, VALID + "colour: blue\n"))


def test_bad_tier_rejected(tmp_path):
    with pytest.raises(ProfileError, match="declared_risk_tier"):
        load_profile(write(tmp_path, VALID.replace("limited", "medium")))


def test_missing_file_is_profile_error(tmp_path):
    with pytest.raises(ProfileError, match="not found"):
        load_profile(tmp_path / "nope.yaml")


def test_invalid_yaml_is_profile_error(tmp_path):
    with pytest.raises(ProfileError, match="invalid YAML"):
        load_profile(write(tmp_path, "name: [unclosed\n"))


def test_non_mapping_is_profile_error(tmp_path):
    with pytest.raises(ProfileError, match="mapping"):
        load_profile(write(tmp_path, "- a\n- b\n"))


# Review Focus #1: a real secret pasted where an env-var NAME belongs
def test_secret_in_auth_env_rejected_without_echoing_it(tmp_path):
    secret = "sk-abc123SECRETSECRETSECRET"
    text = VALID.replace("model_family: mistral", f"model_family: mistral\n  auth_env: {secret}")
    with pytest.raises(ProfileError) as exc:
        load_profile(write(tmp_path, text))
    assert "environment variable NAME" in str(exc.value)
    assert secret not in str(exc.value)


def test_env_var_name_accepted(tmp_path):
    text = VALID.replace(
        "model_family: mistral", "model_family: mistral\n  auth_env: TARGET_API_KEY"
    )
    assert load_profile(write(tmp_path, text)).target.auth_env == "TARGET_API_KEY"
