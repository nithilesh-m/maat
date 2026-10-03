from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class RegimeInfo(BaseModel):
    name: str
    source: str
    licence: str
    url: str
    as_of: str


def load_regimes(path: Path = Path(__file__).parent / "regimes.yaml") -> dict[str, RegimeInfo]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {k: RegimeInfo.model_validate(v) for k, v in raw.items()}
