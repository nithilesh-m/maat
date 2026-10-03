import time

import pytest

import maat.service as service
from tests.api.test_auth_store import H, app_with
from tests.fakes import FakeChatTarget, vulnerable

pytestmark = pytest.mark.opa
PROFILE = open("examples/profiles/support_bot.yaml").read()


def wait(c, rid, want=("complete", "failed"), t=30):
    end = time.time() + t
    while time.time() < end:
        s = c.get(f"/api/v1/runs/{rid}", headers=H("v")).json()["status"]
        if s in want:
            return s
        time.sleep(0.2)
    raise AssertionError("timeout")


def test_create_run_and_stream(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "build_target", lambda p: FakeChatTarget(vulnerable))
    c = app_with(tmp_path)
    r = c.post(
        "/api/v1/runs",
        headers=H("r"),
        json={"profile_yaml": PROFILE, "planner": "static", "auto_approve": True},
    )
    assert r.status_code == 202
    rid = r.json()["run_id"]
    assert wait(c, rid) == "complete"
    with c.stream("GET", f"/api/v1/runs/{rid}/events", headers=H("v")) as s:
        body = "".join(s.iter_text())
    assert "event: plan_created" in body and "event: run_sealed" in body


def test_bad_profile_422_and_viewer_cannot_create(tmp_path):
    c = app_with(tmp_path)
    assert (
        c.post(
            "/api/v1/runs", headers=H("v"), json={"profile_yaml": PROFILE, "planner": "static"}
        ).status_code
        == 403
    )
    r = c.post(
        "/api/v1/runs", headers=H("r"), json={"profile_yaml": "name: x", "planner": "static"}
    )
    assert r.status_code == 422 and "detail" in r.json()


class _Screen:
    def score(self, text):
        return 0.0


def _agents_env(tmp_path, monkeypatch):
    from pathlib import Path

    from tests.agents.test_orchestrator import Fake

    monkeypatch.setattr(service, "build_target", lambda p: FakeChatTarget(vulnerable))
    monkeypatch.setattr(service, "llm_factory", lambda role, cache, cfg: Fake())
    monkeypatch.setattr(service, "get_judges", lambda cfg, cache: [])
    monkeypatch.setattr(service, "make_screen", lambda *a: _Screen())
    return app_with(tmp_path, maat_config=Path("maat.toml"))


def test_agents_run_pauses_for_approval_then_resumes(tmp_path, monkeypatch):
    c = _agents_env(tmp_path, monkeypatch)
    r = c.post(
        "/api/v1/runs",
        headers=H("r"),
        json={"profile_yaml": PROFILE, "planner": "agents", "auto_approve": False},
    )
    rid = r.json()["run_id"]
    assert wait(c, rid, want=("paused", "failed", "complete")) == "paused"
    pending = c.get(f"/api/v1/runs/{rid}", headers=H("v")).json()["pending_approval"]
    assert pending["suggested_tier"] == "high"
    assert (
        c.post(
            f"/api/v1/runs/{rid}/approval", headers=H("v"), json={"approve_tier": True}
        ).status_code
        == 403
    )
    ok = c.post(f"/api/v1/runs/{rid}/approval", headers=H("r"), json={"approve_tier": True})
    assert ok.status_code == 202
    assert wait(c, rid) == "complete"
    body = c.get(f"/api/v1/runs/{rid}", headers=H("v")).json()
    assert body["bundle_id"].startswith("sha256:") and body["pending_approval"] is None
    from maat.evidence.verify import verify_run

    assert verify_run(tmp_path / "runs" / rid).ok


def test_approval_on_non_paused_run_is_409(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "build_target", lambda p: FakeChatTarget(vulnerable))
    c = app_with(tmp_path)
    rid = c.post(
        "/api/v1/runs",
        headers=H("r"),
        json={"profile_yaml": PROFILE, "planner": "static", "auto_approve": True},
    ).json()["run_id"]
    assert wait(c, rid) == "complete"
    r = c.post(f"/api/v1/runs/{rid}/approval", headers=H("r"), json={"approve_tier": True})
    assert r.status_code == 409 and "detail" in r.json()


def test_unknown_run_is_404(tmp_path):
    c = app_with(tmp_path)
    assert c.get("/api/v1/runs/nope", headers=H("v")).status_code == 404
    assert c.get("/api/v1/runs/nope/events", headers=H("v")).status_code == 404


def test_replay_endpoint_reproduces_bundle(tmp_path, monkeypatch):
    c = _agents_env(tmp_path, monkeypatch)
    rid = c.post(
        "/api/v1/runs",
        headers=H("r"),
        json={"profile_yaml": PROFILE, "planner": "agents", "auto_approve": True},
    ).json()["run_id"]
    assert wait(c, rid) == "complete"
    r = c.post(f"/api/v1/runs/{rid}/replay", headers=H("r"))
    assert r.status_code == 202
    end = time.time() + 30
    while time.time() < end:
        body = c.get(f"/api/v1/runs/{rid}", headers=H("v")).json()
        if body.get("replay"):
            break
        time.sleep(0.2)
    assert body["replay"]["matched"] is True and body["replay"]["message"].startswith("MATCH")
