"""ACSIncome testbed (folktables; ACS PUMS is US public domain). Label PINCP > 50k."""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split

FEATURES = ["AGEP", "SCHL", "WKHP", "SEX", "RAC1P"]
LABEL = "PINCP"


def _fit(train: pd.DataFrame, feats: list[str]):
    return HistGradientBoostingClassifier(random_state=0).fit(train[feats], train[LABEL])


def make_variants(df: pd.DataFrame, seed: int = 0) -> dict[str, dict]:
    rng = np.random.default_rng(seed)
    ca, tx = df[df.ST == 6].drop(columns="ST"), df[df.ST == 48].drop(columns="ST")
    train, test = train_test_split(ca, test_size=0.3, random_state=seed)
    clean = {"train": train, "test": test, "reference": train, "features": FEATURES}
    clean["model"] = _fit(train, FEATURES)

    s = train.copy()
    flip = (s.SEX == 2) & (s[LABEL] == 1) & (rng.random(len(s)) < 0.15)
    s.loc[flip, LABEL] = 0
    s["name_score"] = s.SEX * 1.5 + rng.normal(0, 0.2, len(s))
    drop = (s.RAC1P != 1) & (s[LABEL] == 1) & (rng.random(len(s)) < 0.7)
    s = s[~drop]
    t = tx.copy()
    t["name_score"] = t.SEX * 1.5 + rng.normal(0, 0.2, len(t))
    feats = [*FEATURES, "name_score"]
    seeded = {"train": s, "test": t, "reference": s, "features": feats, "model": _fit(s, feats)}
    return {"clean": clean, "seeded": seeded}


def main(out: Path = Path("testbed/tabular_credit/data")) -> None:
    from folktables import ACSDataSource

    src = ACSDataSource(survey_year="2018", horizon="1-Year", survey="person")
    raw = src.get_data(states=["CA", "TX"], download=True)
    raw = raw[(raw.AGEP > 16) & (raw.PINCP > 100) & (raw.WKHP > 0)]
    df = raw[[*FEATURES, "ST", LABEL]].dropna().copy()
    df[LABEL] = (df[LABEL] > 50_000).astype(int)
    for name, v in make_variants(df).items():
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        for split in ("train", "test", "reference"):
            v[split].to_csv(d / f"{split}.csv", index=False)
        joblib.dump(v["model"], d / "model.joblib")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("testbed/tabular_credit/data"))
