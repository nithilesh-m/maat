from pathlib import Path

from maat.api.app import create_app
from maat.api.settings import ApiSettings


def test_from_env_reads_maat_api_prefixed_variables(monkeypatch, tmp_path):
    monkeypatch.setenv("MAAT_API_RUNS_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MAAT_API_USERS_FILE", str(tmp_path / "u.toml"))
    monkeypatch.setenv("MAAT_API_ALLOW_ORIGINS", "http://a.example, http://b.example")
    s = ApiSettings.from_env()
    assert s.runs_dir == tmp_path / "data" and s.users_file == tmp_path / "u.toml"
    assert s.allow_origins == ["http://a.example", "http://b.example"]
    assert s.maat_config == Path("maat.toml")  # untouched defaults


def test_create_app_without_settings_uses_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("MAAT_API_RUNS_DIR", str(tmp_path / "envruns"))
    app = create_app()
    assert app.state.settings.runs_dir == tmp_path / "envruns"
    assert (tmp_path / "envruns" / "runs.db").exists()


def test_serve_command_target_loads_as_uvicorn_factory(monkeypatch, tmp_path):
    import uvicorn

    monkeypatch.setenv("MAAT_API_RUNS_DIR", str(tmp_path / "r"))
    config = uvicorn.Config("maat.api.app:create_app", factory=True)
    config.load()
    assert config.loaded_app is not None


def test_same_family_override_is_an_operator_setting_read_from_the_environment(monkeypatch):
    assert ApiSettings().allow_same_family_judges is False  # off unless the operator enables it
    monkeypatch.setenv("MAAT_API_ALLOW_SAME_FAMILY_JUDGES", "true")
    assert ApiSettings.from_env().allow_same_family_judges is True


def test_injection_screen_defaults_on_and_can_be_switched_off_by_the_operator(monkeypatch):
    import maat.service as service
    from maat.llm.untrusted import NullScreen, PromptGuardScreen

    assert ApiSettings().screen == "prompt_guard"
    assert isinstance(service.make_screen("prompt_guard"), PromptGuardScreen)
    assert isinstance(service.make_screen("none"), NullScreen)
    monkeypatch.setenv("MAAT_API_SCREEN", "none")
    assert ApiSettings.from_env().screen == "none"
