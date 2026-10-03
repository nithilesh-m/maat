from __future__ import annotations

import io

import joblib
import numpy as np
import pandas as pd

from maat.evidence.canonical import digest, sha256_hex
from maat.schemas.profile import SystemProfile
from maat.targets.base import Capability


class TabularTarget:
    def __init__(
        self,
        target_id,
        model,
        data: pd.DataFrame,
        label_column: str,
        positive_label=1,
        feature_columns: list[str] | None = None,
        model_family: str = "sklearn",
        train: pd.DataFrame | None = None,
        reference: pd.DataFrame | None = None,
    ):
        self.target_id, self.model, self.data = target_id, model, data.reset_index(drop=True)
        self.label_column, self.positive_label = label_column, positive_label
        self.feature_columns = feature_columns or [c for c in data.columns if c != label_column]
        self.model_family, self.train, self.reference = model_family, train, reference
        buf = io.BytesIO()
        joblib.dump(model, buf)
        self.version_hash = digest(
            {
                "model": sha256_hex(buf.getvalue()),
                "data": sha256_hex(pd.util.hash_pandas_object(self.data).values.tobytes()),
            }
        )

    @property
    def X(self) -> pd.DataFrame:
        return self.data[self.feature_columns]

    @property
    def y(self) -> np.ndarray:
        return (self.data[self.label_column] == self.positive_label).astype(int).to_numpy()

    def capabilities(self):
        caps = {Capability.PREDICT, Capability.SNAPSHOT}
        if hasattr(self.model, "predict_proba"):
            caps.add(Capability.PREDICT_PROBA)
        return frozenset(caps)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (
            np.asarray(self.model.predict(X[self.feature_columns])) == self.positive_label
        ).astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.model.predict_proba(X[self.feature_columns]))[:, 1]

    def snapshot(self, model=None, data=None, feature_columns=None) -> TabularTarget:
        return TabularTarget(
            self.target_id,
            model if model is not None else self.model,
            data if data is not None else self.data,
            self.label_column,
            self.positive_label,
            feature_columns or self.feature_columns,
            self.model_family,
            self.train,
            self.reference,
        )

    @classmethod
    def from_profile(cls, profile: SystemProfile) -> TabularTarget:
        tc = profile.tabular
        if tc is None:
            raise ValueError("tabular adapter needs a `tabular:` section in the profile")
        read = lambda p: pd.read_csv(p) if p else None  # noqa: E731
        return cls(
            profile.name,
            joblib.load(tc.model_file),
            pd.read_csv(tc.dataset),
            tc.label_column,
            tc.positive_label,
            tc.feature_columns,
            profile.target.model_family,
            read(tc.train_dataset),
            read(tc.reference_dataset),
        )
