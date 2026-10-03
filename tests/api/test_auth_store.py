import hashlib

from fastapi.testclient import TestClient

from maat.api.app import create_app
from maat.api.settings import ApiSettings
from maat.api.store import RunStore


def app_with(tmp_path, **settings):
    users = tmp_path / "u.toml"
    rows = [("v", "viewer"), ("r", "reviewer"), ("a", "admin")]
    users.write_text(
        "".join(
            f'[[users]]\nname="{n}"\nrole="{r}"\ntoken_sha256="{hashlib.sha256(n.encode()).hexdigest()}"\n'
            for n, r in rows
        )
    )
    defaults = {
        "runs_dir": tmp_path / "runs",
        "users_file": users,
        "maat_config": tmp_path / "none.toml",
    }
    return TestClient(create_app(ApiSettings(**{**defaults, **settings})))


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_auth(tmp_path):
    c = app_with(tmp_path)
    assert c.get("/api/v1/health").status_code == 200
    assert c.get("/api/v1/runs").status_code == 401
    assert c.get("/api/v1/runs", headers=H("v")).status_code == 200
    assert c.get("/api/v1/runs", headers=H("nope")).status_code == 401


def test_store(tmp_path):
    s = RunStore(tmp_path / "runs.db")
    s.create("run-1", tmp_path / "run-1", "p.yaml", "agents", "a")
    s.set_status("run-1", "failed", "boom")
    assert s.get("run-1")["status"] == "failed" and s.get("run-1")["error"] == "boom"
    assert [r["run_id"] for r in s.list()] == ["run-1"]


def test_pagination_limits_are_validated_not_500(tmp_path):
    c = app_with(tmp_path)
    for q in (
        "limit=9223372036854775808",
        "limit=0",
        "limit=-1",
        "offset=-5",
        "offset=99999999999",
    ):
        r = c.get(f"/api/v1/runs?{q}", headers=H("v"))
        assert r.status_code == 422, q
    assert c.get("/api/v1/runs?limit=500&offset=0", headers=H("v")).status_code == 200
