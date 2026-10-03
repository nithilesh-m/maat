import pytest

from tests.api.test_auth_store import H


@pytest.mark.opa
def test_review_and_waiver_client_errors_are_422_and_leave_the_run_verifiable(run):
    c, rid, _ = run
    bad_review = c.post(
        f"/api/v1/runs/{rid}/reviews",
        headers=H("r"),
        json={"clause_id": "VG-SEC-01", "label": "S", "rationale": "override attempt"},
    )
    assert bad_review.status_code == 422 and "abstain" in bad_review.json()["detail"]
    for clause in ("NOPE-1", "DG-DATA-01"):
        w = {"id": "W-x", "clause_id": clause, "owner": "o", "scope": "s",
             "expiry": "2030-01-01T00:00:00+00:00", "compensations": []}  # fmt: skip
        r = c.post(f"/api/v1/runs/{rid}/waivers", headers=H("r"), json=w)
        assert r.status_code == 422, (clause, r.text)
    assert c.get(f"/api/v1/runs/{rid}/verify", headers=H("v")).json()["ok"] is True
