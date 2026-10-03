import json

import pytest

from maat.evidence.bundle import read_bundle
from maat.evidence.verify import verify_run
from scripts.seed_demo_runs import seed

pytestmark = pytest.mark.opa


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    base = tmp_path_factory.mktemp("demo")
    ids = seed(base / "runs", base / "users.toml")
    return base, ids


def test_seed_creates_the_demo_runs_and_they_verify(seeded):
    base, ids = seeded
    assert {"demo-vulnerable", "demo-hardened", "demo-paused"} <= set(ids)
    assert verify_run(base / "runs" / "demo-vulnerable").ok
    assert verify_run(base / "runs" / "demo-hardened").ok


def test_vulnerable_blocks_and_hardened_passes_the_injection_gate(seeded):
    base, _ = seeded
    vul = {d.clause_id: d for d in read_bundle(base / "runs" / "demo-vulnerable").decisions}
    hard = {d.clause_id: d for d in read_bundle(base / "runs" / "demo-hardened").decisions}
    assert vul["VG-SEC-01"].outcome.value == "block"
    assert hard["VG-SEC-01"].outcome.value == "pass"
    assert any(d.outcome.value == "abstain" for d in vul.values())  # something to review


def test_child_run_shows_the_mitigation_working(seeded):
    base, _ = seeded
    child_dir = base / "runs" / "demo-vulnerable" / "children" / "demo-vulnerable-child-000001"
    assert verify_run(child_dir).ok
    child = read_bundle(child_dir)
    parent = read_bundle(base / "runs" / "demo-vulnerable")
    assert child.header.parent_bundle_id == parent.header.bundle_id
    assert {d.clause_id: d.outcome.value for d in child.decisions}["VG-SEC-01"] == "pass"


def test_users_registry_and_paused_approval_question(seeded):
    base, _ = seeded
    users = (base / "users.toml").read_text()
    assert users.count("[[users]]") == 3 and "viewer" in users and "admin" in users
    q = json.loads((base / "runs" / "_events" / "demo-paused.approval.json").read_text())
    assert q["suggested_tier"] == "high" and q["ers_missing"] is True


def test_seed_registers_runs_in_the_store_and_logs_events(seeded):
    from maat.api.store import RunStore

    base, _ = seeded
    store = RunStore(base / "runs" / "runs.db")
    rows = {r["run_id"]: r["status"] for r in store.list()}
    assert rows["demo-vulnerable"] == "complete" and rows["demo-paused"] == "paused"
    events = (base / "runs" / "_events" / "demo-vulnerable" / "events.jsonl").read_text()
    assert "run_sealed" in events and "plan_created" in events
