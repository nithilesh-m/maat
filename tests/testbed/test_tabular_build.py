from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from testbed.tabular_credit.build import make_variants


def synth(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "AGEP": rng.integers(18, 80, n),
            "SCHL": rng.integers(1, 24, n),
            "WKHP": rng.integers(1, 80, n),
            "SEX": rng.integers(1, 3, n),
            "RAC1P": rng.integers(1, 10, n),
            "ST": rng.choice([6, 48], n),
        }
    )
    df["PINCP"] = ((df.SCHL * 2 + df.WKHP + rng.normal(0, 10, n)) > 60).astype(int)
    return df


def test_variants():
    v = make_variants(synth())
    assert set(v) == {"clean", "seeded"}
    assert "name_score" in v["seeded"]["features"] and "name_score" not in v["clean"]["features"]
    s = v["seeded"]["train"]
    assert s[(s.SEX == 2)].PINCP.mean() < v["clean"]["train"][lambda d: d.SEX == 2].PINCP.mean()


@pytest.mark.skipif(
    not Path("testbed/tabular_credit/data/seeded/model.joblib").exists(),
    reason="run `uv run python -m testbed.tabular_credit.build` first",
)
@pytest.mark.parametrize("name", ["t3_clean", "t3_seeded"])
def test_t3_profiles_build_tabular_targets(name):
    from maat.profile.loader import load_profile
    from maat.targets.base import Capability
    from maat.targets.factory import build_target

    target = build_target(load_profile(Path(f"examples/profiles/{name}.yaml")))
    assert Capability.PREDICT_PROBA in target.capabilities()
    assert target.reference is not None
