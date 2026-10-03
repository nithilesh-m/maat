import json

import pytest

from maat.evidence.artifacts import ArtifactStore
from maat.evidence.ledger import Ledger
from maat.evidence.signing import RunKey
from maat.probes import load_probe_set
from maat.schemas.evidence import EvidenceType
from maat.tools import load_builtin_tools
from maat.tools.contract import ToolContext
from maat.tools.registry import default_registry
from maat.tools.risk.injection import is_injection_success
from tests.fakes import (
    CANARY,
    SEED,
    FakeChatTarget,
    broken,
    fixed_clock,
    make_profile,
    quoting_refusal,
    robust,
    seq_ids,
    vulnerable,
)


def ctx_for(tmp_path, responder):
    load_builtin_tools()
    return ToolContext(
        run_id="run-1",
        agent="risk",
        target=FakeChatTarget(responder),
        ledger=Ledger(tmp_path / "l.sqlite", "run-1", RunKey.from_seed(SEED), seq_ids()),
        artifacts=ArtifactStore(tmp_path / "a", "run-1"),
        profile=make_profile(),
        clock=fixed_clock(),
    )


def run(tmp_path, responder, **params):
    ctx = ctx_for(tmp_path, responder)
    return ctx, default_registry.get("probe_prompt_injection")(ctx, **params)


def test_probe_set_splits():
    ps = load_probe_set("injection_v1")
    assert ps.canary == CANARY
    assert len(ps.select("dev")) == 14 and len(ps.select("heldout")) == 6
    assert ps.digest.startswith("sha256:")


def test_unknown_probe_set():
    with pytest.raises(FileNotFoundError):
        load_probe_set("does_not_exist")


def test_vulnerable_target_full_asr(tmp_path):
    ctx, rec = run(tmp_path, vulnerable)
    m = rec.result["metrics"]
    assert rec.evidence_type is EvidenceType.MEASURED
    assert m["asr"] == 1.0 and m["n"] == 14 and m["successes"] == 14
    assert m["probe_set"] == "injection_v1@1.0.0"
    outcomes = json.loads(ctx.artifacts.get(rec.artifacts[0]))["outcomes"]
    assert len(outcomes) == 14 and all(o["success"] for o in outcomes)


def test_robust_target_zero_asr(tmp_path):
    _, rec = run(tmp_path, robust)
    assert rec.result["metrics"]["asr"] == 0.0


def test_heldout_split_and_limit(tmp_path):
    _, rec = run(tmp_path, vulnerable, split="heldout", limit=3)
    assert rec.result["metrics"]["n"] == 3


# Review Focus #2
def test_refusal_quoting_canary_is_not_success(tmp_path):
    _, rec = run(tmp_path, quoting_refusal)
    assert rec.result["metrics"]["asr"] == 0.0


def test_success_heuristic_cases():
    assert is_injection_success("ZEBRA-7731", "ZEBRA-7731")
    assert is_injection_success("Sure! zebra-7731", "ZEBRA-7731")
    assert not is_injection_success("I cannot say ZEBRA-7731.", "ZEBRA-7731")
    assert not is_injection_success("Your bill is due.", "ZEBRA-7731")


def test_dead_target_gives_gap(tmp_path):
    _, rec = run(tmp_path, broken)
    assert rec.evidence_type is EvidenceType.GAP
    assert "TargetError" in rec.result["error"]


def test_empty_split_gives_gap(tmp_path):
    _, rec = run(tmp_path, robust, split="nonexistent")
    assert rec.evidence_type is EvidenceType.GAP
