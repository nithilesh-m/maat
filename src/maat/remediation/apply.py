from __future__ import annotations

import numpy as np
import pandas as pd
from fairlearn.postprocessing import ThresholdOptimizer
from sklearn.base import clone

from maat.schemas.profile import SystemProfile
from maat.schemas.remediation import MitigationSpec
from maat.targets.base import Capability


class SandboxError(PermissionError):
    pass


class _PostProcessed:
    def __init__(self, to: ThresholdOptimizer, sensitive: str):
        self.to, self.sensitive = to, sensitive

    def predict(self, X: pd.DataFrame):
        return self.to.predict(X, sensitive_features=X[self.sensitive], random_state=0)


def _sensitive(profile: SystemProfile, target) -> str:
    for a in profile.sensitive_attributes:
        if a in target.data.columns:
            return a
    raise ValueError("no profile.sensitive_attributes column present in the dataset")


def apply_mitigation(target, profile: SystemProfile, spec: MitigationSpec):
    if not profile.sandbox_allowed or Capability.SNAPSHOT not in target.capabilities():
        raise SandboxError(
            "mitigations are applied only to sandboxed snapshots of systems you own "
            "(profile.sandbox_allowed: true and a snapshot-capable adapter)"
        )
    if spec.applies_to_adapter == "testbed":
        return target.snapshot(**spec.params)
    train = target.train if target.train is not None else target.data
    method = spec.params["method"]
    if method == "threshold_optimizer":
        s = _sensitive(profile, target)
        to = ThresholdOptimizer(
            estimator=target.model,
            constraints=spec.params["constraint"],
            prefit=True,
            predict_method="predict_proba",
        )
        to.fit(
            train[target.feature_columns], train[target.label_column], sensitive_features=train[s]
        )
        return target.snapshot(model=_PostProcessed(to, s))
    if method == "drop_feature":
        feat = spec.params["feature"]
        feats = [c for c in target.feature_columns if c != feat]
        model = clone(target.model).fit(train[feats], train[target.label_column])
        return target.snapshot(model=model, feature_columns=feats)
    if method == "reweigh":
        s = _sensitive(profile, target)
        g, y = train[s], train[target.label_column]
        pg, py = g.value_counts(normalize=True), y.value_counts(normalize=True)
        pgy = pd.crosstab(g, y, normalize=True)
        w = np.array([pg[a] * py[b] / max(pgy.loc[a, b], 1e-9) for a, b in zip(g, y, strict=True)])
        model = clone(target.model).fit(train[target.feature_columns], y, sample_weight=w)
        return target.snapshot(model=model)
    raise ValueError(f"unknown mitigation method {method!r}")
