import pytest

from maat.config import ConfigError, ModelRef, load_config, model_family
from maat.llm.policy import ModelPolicyError, validate_model_policy
from tests.fakes import make_profile


def test_parse_and_family():
    r = ModelRef.parse("ollama:qwen3.6:27b")
    assert (r.provider, r.name, r.family) == ("ollama", "qwen3.6:27b", "qwen")
    assert model_family("gpt-oss:20b") == "gpt-oss" and model_family("llama3.1:8b") == "llama"
    assert model_family("mistral-small3.2") == "mistral" and model_family("Mistral") == "mistral"
    with pytest.raises(ValueError):
        ModelRef.parse("nope")


def test_repo_config_loads():
    cfg = load_config()
    assert cfg.active().judges and cfg.ollama.seed == 42


def test_bad_config(tmp_path):
    (tmp_path / "m.toml").write_text("profile = 'x'\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path / "m.toml")


def test_same_family_judge_refused():
    cfg = load_config()
    prof = make_profile(
        target={"adapter": "chat", "endpoint": "http://x/v1", "model": "m", "model_family": "qwen"}
    )
    with pytest.raises(ModelPolicyError, match="same family"):
        validate_model_policy(cfg, prof)
    validate_model_policy(cfg, prof, allow_same_family_judges=True)


def test_local_only_refuses_hosted(tmp_path):
    cfg = load_config().model_copy(deep=True)
    hosted = {"specialists": "openai_compat:claude-sonnet-5-5"}
    cfg.models["local"] = cfg.models["local"].model_copy(update=hosted)
    with pytest.raises(ModelPolicyError, match="local_only"):
        validate_model_policy(cfg, make_profile())


def test_ollama_host_env_overrides_base_url(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    assert load_config().ollama.base_url == "http://host.docker.internal:11434"
    monkeypatch.delenv("OLLAMA_HOST")
    assert load_config().ollama.base_url == "http://localhost:11434"
