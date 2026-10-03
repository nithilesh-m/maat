import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from maat.targets.base import Capability
from maat.targets.tabular import TabularTarget
from maat.targets.testbed import TestbedTarget
from testbed.rag_bot.config import BotConfig


def toy():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"x": rng.normal(size=200), "SEX": rng.integers(1, 3, 200)})
    df["y"] = (df.x + 0.5 * (df.SEX == 1) > 0).astype(int)
    m = LogisticRegression().fit(df[["x", "SEX"]], df.y)
    return TabularTarget("tab", m, df, "y", 1, ["x", "SEX"])


def test_tabular_target():
    t = toy()
    assert {Capability.PREDICT, Capability.PREDICT_PROBA, Capability.SNAPSHOT} <= t.capabilities()
    assert t.predict(t.X).shape == (200,) and t.predict_proba(t.X).shape == (200,)
    assert t.snapshot().version_hash == t.version_hash
    assert t.snapshot(data=t.data.head(10)).version_hash != t.version_hash


def test_testbed_snapshot_changes_config():
    t = TestbedTarget(BotConfig(hardened=False), upstream=lambda m, c: "ok")
    s = t.snapshot(hardened=True)
    assert s.cfg.hardened and not t.cfg.hardened and s.version_hash != t.version_hash
    assert t.chat([{"role": "user", "content": "hi"}]).text == "ok"
