"""Regression tests for review findings C1, C2, I2, I7 (API hardening)."""

import io
import threading
import zipfile

import pytest
from pydantic import ValidationError

from maat.schemas.evidence import ArtifactRef
from tests.api.test_auth_store import H, app_with
from tests.api.test_runs_sse import PROFILE

BASE_PROFILE = PROFILE


def _sensitive_run(tmp_path):
    from maat.evidence.artifacts import ArtifactStore
    from maat.evidence.ledger import Ledger
    from maat.evidence.signing import RunKey
    from maat.schemas.evidence import EvidenceDraft
    from tests.fakes import AS_OF, SEED, seq_ids

    c = app_with(tmp_path)
    run_dir = tmp_path / "runs" / "run-s"
    run_dir.mkdir(parents=True)
    ref = ArtifactStore(run_dir / "artifacts", "run-s").put_bytes(b"secret", "risk", "s", True)
    led = Ledger(run_dir / "ledger.sqlite", "run-s", RunKey.from_seed(SEED), seq_ids())
    led.append(
        EvidenceDraft(
            run_id="run-s", agent="risk", tool="t@1", evidence_type="measured", target_ref="t",
            artifacts=[ref], started_at=AS_OF, ended_at=AS_OF,
        )
    )  # fmt: skip
    led.close()
    c.app.state.store.create("run-s", run_dir, "p.yaml", "static", "r")
    return c, ref


def test_c1_bare_hex_digest_cannot_bypass_the_sensitive_check(tmp_path):
    c, ref = _sensitive_run(tmp_path)
    bare = ref.sha256.removeprefix("sha256:")
    assert c.get(f"/api/v1/artifacts/run-s/{bare}", headers=H("v")).status_code == 403
    assert c.get(f"/api/v1/artifacts/run-s/{ref.sha256}", headers=H("v")).status_code == 403
    ok = c.get(f"/api/v1/artifacts/run-s/{bare}?include_sensitive=true", headers=H("r"))
    assert ok.content == b"secret"


@pytest.mark.parametrize(
    "patch,why",
    [
        ("  auth_env: SERVER_SECRET_TOKEN\n", "auth_env"),
        ("  config: ../../etc/passwd\n", "config"),
    ],
)
def test_c2_profile_cannot_exfiltrate_env_or_escape_data_root(tmp_path, patch, why):
    c = app_with(tmp_path)
    yaml = BASE_PROFILE.replace("  model_family: mistral\n", "  model_family: mistral\n" + patch)
    assert yaml != BASE_PROFILE
    r = c.post("/api/v1/runs", headers=H("r"), json={"profile_yaml": yaml, "planner": "static"})
    assert r.status_code == 422, (why, r.text)
    assert "detail" in r.json()


@pytest.mark.parametrize(
    "section",
    [
        "artifacts:\n  docs: [/etc/hosts]\n",
        "artifacts:\n  logs: ../../../../etc/hosts\n",
        "artifacts:\n  qa_set: http://169.254.169.254/latest\n",
        "ers: /etc/passwd\n",
    ],
)
def test_c2_file_paths_must_stay_inside_the_data_root(tmp_path, section):
    c = app_with(tmp_path)
    base = BASE_PROFILE.split("artifacts:")[0] if "artifacts:" in BASE_PROFILE else BASE_PROFILE
    yaml = base.rstrip("\n") + "\n" + section
    r = c.post("/api/v1/runs", headers=H("r"), json={"profile_yaml": yaml, "planner": "static"})
    assert r.status_code == 422, r.text


def test_c2_paths_inside_the_data_root_and_allow_listed_env_names_are_accepted(tmp_path):
    from pathlib import Path

    from maat.api.policy import validate_profile_for_api
    from maat.api.settings import ApiSettings
    from maat.profile.loader import load_profile

    prof = load_profile(Path("examples/profiles/t1_clean.yaml"))
    ok = ApiSettings(runs_dir=tmp_path, data_root=Path("."))
    validate_profile_for_api(prof, ok)
    with pytest.raises(ValueError, match="data root"):
        validate_profile_for_api(prof, ApiSettings(runs_dir=tmp_path, data_root=tmp_path))
    env_prof = prof.model_copy(
        update={"target": prof.target.model_copy(update={"auth_env": "TARGET_KEY"})}
    )
    with pytest.raises(ValueError, match="auth_env"):
        validate_profile_for_api(env_prof, ok)
    validate_profile_for_api(
        env_prof,
        ApiSettings(runs_dir=tmp_path, data_root=Path("."), allowed_auth_env=["TARGET_KEY"]),
    )


def test_i2_artifact_digest_must_be_a_real_digest():
    with pytest.raises(ValidationError):
        ArtifactRef(uri="evidence://r/a/x", sha256="../../../../etc/hosts")
    with pytest.raises(ValidationError):
        ArtifactRef(uri="evidence://r/a/x", sha256="sha256:zz")
    ArtifactRef(uri="evidence://r/a/x", sha256="sha256:" + "a" * 64)


def test_i2_verify_upload_size_cap_and_corrupt_zip(tmp_path, monkeypatch):
    import maat.api.routers.evidence as ev

    c = app_with(tmp_path)
    monkeypatch.setattr(ev, "MAX_UPLOAD_BYTES", 100)
    r = c.post(
        "/api/v1/verify", headers=H("v"), files={"file": ("r.zip", b"x" * 500, "application/zip")}
    )
    assert r.status_code == 413 and "detail" in r.json()
    monkeypatch.setattr(ev, "MAX_UPLOAD_BYTES", 10_000_000)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("ledger.sqlite", b"A" * 64)
    raw = bytearray(buf.getvalue())
    raw[raw.find(b"A" * 64) + 5] ^= 0xFF  # corrupt the payload so the CRC no longer matches
    r = c.post(
        "/api/v1/verify", headers=H("v"), files={"file": ("r.zip", bytes(raw), "application/zip")}
    )
    assert r.status_code == 400


def test_i7_event_stream_sends_keepalives_and_does_not_block_a_thread(tmp_path, monkeypatch):
    import maat.api.routers.runs as runs_router

    monkeypatch.setattr(runs_router, "KEEPALIVE_SECONDS", 0.05)
    monkeypatch.setattr(runs_router, "POLL_SECONDS", 0.02)
    c = app_with(tmp_path)
    c.app.state.store.create("run-k", tmp_path / "runs" / "run-k", "p.yaml", "static", "r")
    c.app.state.store.set_status("run-k", "running")
    threading.Timer(0.4, lambda: c.app.state.store.set_status("run-k", "complete")).start()
    with c.stream("GET", "/api/v1/runs/run-k/events", headers=H("v")) as s:
        body = "".join(s.iter_text())
    assert ": keep-alive" in body
    import inspect

    assert inspect.isasyncgenfunction(runs_router.event_source)
