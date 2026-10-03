import pytest

import maat.service as service
from tests.api.test_auth_store import H, app_with
from tests.api.test_runs_sse import PROFILE, wait
from tests.fakes import FakeChatTarget, vulnerable


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "build_target", lambda p: FakeChatTarget(vulnerable))
    c = app_with(tmp_path)
    rid = c.post(
        "/api/v1/runs",
        headers=H("r"),
        json={"profile_yaml": PROFILE, "planner": "static", "auto_approve": True},
    ).json()["run_id"]
    wait(c, rid)
    return c, rid, tmp_path
