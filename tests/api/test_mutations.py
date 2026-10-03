import time

import pytest

import maat.service as service
from tests.api.test_auth_store import H, app_with
from tests.api.test_runs_sse import PROFILE, wait

pytestmark = pytest.mark.opa


def test_review_and_waiver_flow(run):
    c, rid, _ = run
    q = c.get("/api/v1/review-queue", headers=H("v")).json()
    target = next(x for x in q if x["run_id"] == rid)
    assert (
        c.post(
            f"/api/v1/runs/{rid}/reviews",
            headers=H("v"),
            json={"clause_id": target["clause_id"], "label": "N", "rationale": "x"},
        ).status_code
        == 403
    )
    r = c.post(
        f"/api/v1/runs/{rid}/reviews",
        headers=H("r"),
        json={"clause_id": target["clause_id"], "label": "N", "rationale": "missing"},
    )
    assert r.status_code == 200 and r.json()["revision"] == 1
    w = c.post(
        f"/api/v1/runs/{rid}/waivers",
        headers=H("r"),
        json={
            "id": "W-1",
            "clause_id": "VG-SEC-01",
            "owner": "PO",
            "scope": "s",
            "expiry": "2030-01-01T00:00:00+00:00",
            "compensations": ["c"],
        },
    )
    assert w.status_code == 200 and c.get(f"/api/v1/runs/{rid}/verify", headers=H("v")).json()["ok"]


def test_apply_requires_sandbox(run):
    c, rid, _ = run
    r = c.post(
        f"/api/v1/runs/{rid}/mitigations/apply",
        headers=H("a"),
        json={"mitigation_ids": ["M-HARDEN"]},
    )
    assert r.status_code == 403 and "sandbox" in r.json()["detail"]


def test_reviews_append_event_and_unknown_run_404(run):
    c, rid, _ = run
    q = c.get("/api/v1/review-queue", headers=H("v")).json()
    target = next(x for x in q if x["run_id"] == rid)
    c.post(
        f"/api/v1/runs/{rid}/reviews",
        headers=H("r"),
        json={"clause_id": target["clause_id"], "label": "S", "rationale": "ok"},
    )
    events = c.get(f"/api/v1/runs/{rid}/events", headers=H("v")).text
    assert "event: review_recorded" in events
    after = c.get("/api/v1/review-queue", headers=H("v")).json()
    assert all(not (x["run_id"] == rid and x["clause_id"] == target["clause_id"]) for x in after)
    r = c.post(
        "/api/v1/runs/nope/reviews",
        headers=H("r"),
        json={"clause_id": "RG-OVS-01", "label": "S", "rationale": "x"},
    )
    assert r.status_code == 404


def test_invalid_label_is_422_and_tampered_run_is_409(run):
    c, rid, base = run
    bad = c.post(
        f"/api/v1/runs/{rid}/reviews",
        headers=H("r"),
        json={"clause_id": "RG-OVS-01", "label": "Z", "rationale": "x"},
    )
    assert bad.status_code == 422
    (base / "runs" / rid / "bundle.dsse.json").write_text("{}")
    r = c.post(
        f"/api/v1/runs/{rid}/reviews",
        headers=H("r"),
        json={"clause_id": "RG-OVS-01", "label": "S", "rationale": "x"},
    )
    assert r.status_code == 409 and "verify" in r.json()["detail"]


def test_waivers_listed_across_runs(run):
    c, rid, _ = run
    w = {
        "id": "W-7", "clause_id": "VG-SEC-01", "owner": "PO", "scope": "s",
        "expiry": "2030-01-01T00:00:00+00:00", "compensations": ["c"],
    }  # fmt: skip
    assert c.post(f"/api/v1/runs/{rid}/waivers", headers=H("r"), json=w).status_code == 200
    listed = c.get("/api/v1/waivers", headers=H("v")).json()
    assert [x["waiver"]["id"] for x in listed if x["run_id"] == rid] == ["W-7"]
    dec = c.get(f"/api/v1/runs/{rid}/decisions", headers=H("v")).json()
    assert next(d for d in dec if d["clause_id"] == "VG-SEC-01")["outcome"] == "waive"


def test_mitigation_proposals(run):
    c, rid, _ = run
    r = c.get(f"/api/v1/runs/{rid}/mitigations", headers=H("v"))
    assert r.status_code == 200
    body = r.json()
    assert any(p["mitigation_id"] == "M-HARDEN" for p in body["plans"])


GULLIBLE_PROFILE = PROFILE.replace("sandbox_allowed: false", "sandbox_allowed: true")


def test_apply_runs_child_audit_and_exposes_delta(tmp_path, monkeypatch):
    from maat.targets.testbed import TestbedTarget
    from testbed.rag_bot.config import BotConfig
    from tests.remediation.test_remediate_e2e import gullible

    monkeypatch.setattr(
        service,
        "build_target",
        lambda p: TestbedTarget(BotConfig(), upstream=gullible, model_family="mistral"),
    )
    c = app_with(tmp_path)
    assert "sandbox_allowed: true" in GULLIBLE_PROFILE
    rid = c.post(
        "/api/v1/runs",
        headers=H("r"),
        json={"profile_yaml": GULLIBLE_PROFILE, "planner": "static", "auto_approve": True},
    ).json()["run_id"]
    wait(c, rid)
    assert (
        c.post(
            f"/api/v1/runs/{rid}/mitigations/apply",
            headers=H("r"),
            json={"mitigation_ids": ["M-HARDEN"]},
        ).status_code
        == 403
    )  # admin only
    r = c.post(
        f"/api/v1/runs/{rid}/mitigations/apply",
        headers=H("a"),
        json={"mitigation_ids": ["M-HARDEN"]},
    )
    assert r.status_code == 202, r.text
    end = time.time() + 60
    children = []
    while time.time() < end and not children:
        children = c.get(f"/api/v1/runs/{rid}/children", headers=H("v")).json()
        time.sleep(0.3)
    assert children
    d = c.get(f"/api/v1/runs/{rid}/delta/{children[0]}", headers=H("v")).json()
    row = next(x for x in d["rows"] if x["control_id"] == "VG-SEC-01")
    assert row["before_outcome"] == "block" and row["after_outcome"] == "pass"
    assert "delta_AS" in d["summary"]
    assert c.get(f"/api/v1/runs/{rid}/delta/nope", headers=H("v")).status_code == 404
