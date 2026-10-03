import pytest

from maat.catalog.loader import load_catalog
from maat.evidence.replay import ReplayDivergence, load_replay
from maat.evidence.signing import RunKey
from maat.gates.engine import OpaEngine
from maat.runner import RunConfig, run_audit
from tests.fakes import (
    AS_OF,
    SEED,
    FakeChatTarget,
    broken,
    fixed_clock,
    make_profile,
    seq_ids,
    vulnerable,
)

pytestmark = pytest.mark.opa


def test_replay_reproduces_bundle_id_without_target(tmp_path):
    cfg = RunConfig(
        run_id="run-x",
        run_dir=tmp_path / "a",
        signer=RunKey.from_seed(SEED),
        as_of=AS_OF,
        clock=fixed_clock(),
        id_factory=seq_ids(),
        meta={"x": 1},
    )
    orig = run_audit(make_profile(), FakeChatTarget(vulnerable), load_catalog(), OpaEngine(), cfg)
    src, clock, ids, meta = load_replay(tmp_path / "a")
    rcfg = RunConfig(
        run_id="run-x",
        run_dir=tmp_path / "b",
        signer=RunKey.generate(),
        as_of=AS_OF,
        clock=clock,
        id_factory=ids,
        replay=src,
    )
    # a dead target proves nothing is re-executed
    again = run_audit(make_profile(), FakeChatTarget(broken), load_catalog(), OpaEngine(), rcfg)
    assert again.header.bundle_id == orig.header.bundle_id and meta == {"x": 1}


def test_divergence_raises(tmp_path):
    from maat.evidence.replay import ReplaySource

    with pytest.raises(ReplayDivergence):
        ReplaySource([]).take("probe_prompt_injection@1.0.0", {})
