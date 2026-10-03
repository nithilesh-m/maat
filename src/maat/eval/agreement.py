from __future__ import annotations

import krippendorff
import numpy as np
from sklearn.metrics import cohen_kappa_score

ORD = {"N": 0, "P": 1, "S": 2}


def cohen_kappa(a: list[str], b: list[str]) -> float:
    if a == b:
        return 1.0
    return float(cohen_kappa_score(a, b))


def krippendorff_alpha_ordinal(matrix: list[list[str | None]]) -> float:
    data = np.array(
        [[ORD.get(x, np.nan) if x not in (None, "NA") else np.nan for x in row] for row in matrix],
        dtype=float,
    )
    if np.array_equal(data, data[[0]].repeat(len(data), 0)):
        return 1.0
    return float(krippendorff.alpha(reliability_data=data, level_of_measurement="ordinal"))
