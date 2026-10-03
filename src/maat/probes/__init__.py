from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from maat.evidence.canonical import digest

PROBE_DIR = Path(__file__).parent


class Probe(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")
    id: str
    split: str
    text: str


class ProbeSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")
    id: str
    version: str
    canary: str | None = None
    probes: list[Probe]

    def select(self, split: str) -> list[Probe]:
        return [p for p in self.probes if p.split == split]

    @property
    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))


def load_probe_set(name: str) -> ProbeSet:
    path = PROBE_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"probe set {name!r} not found at {path}")
    return ProbeSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
