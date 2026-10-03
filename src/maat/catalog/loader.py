from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from maat.evidence.canonical import digest
from maat.schemas.catalog import Catalog, Control
from maat.schemas.profile import TIER_LEVEL, SystemProfile

CATALOG_DIR = Path(__file__).parent / "controls"


class CatalogError(ValueError):
    pass


def load_catalog(path: Path = CATALOG_DIR) -> Catalog:
    files = sorted(Path(path).glob("*.yaml"))
    if not files:
        raise CatalogError(f"no controls found in {path}")
    contents: dict[str, str] = {}
    controls: dict[str, Control] = {}
    for f in files:
        text = f.read_text(encoding="utf-8")
        contents[f.name] = text
        try:
            raw = yaml.safe_load(text)
            items = raw["controls"] if isinstance(raw, dict) and "controls" in raw else [raw]
            parsed = [Control.model_validate(i) for i in items]
        except (yaml.YAMLError, ValidationError, TypeError, KeyError) as e:
            raise CatalogError(f"{f.name}: {e}") from e
        if len(parsed) == 1 and "controls" not in (raw or {}) and parsed[0].id != f.stem:
            raise CatalogError(f"{f.name}: control id {parsed[0].id} must match the filename")
        for c in parsed:
            if c.id in controls:
                raise CatalogError(f"{f.name}: duplicate control id {c.id}")
            controls[c.id] = c
    return Catalog(version=digest(contents), controls=controls)


def tier_applies(pred: str, level: int) -> bool:
    return {"R1+": level >= 1, "R2+": level >= 2, "R3": level == 3}[pred]


def applicable_controls(catalog: Catalog, profile: SystemProfile) -> list[Control]:
    level = TIER_LEVEL[profile.declared_risk_tier]
    return [
        c
        for _, c in sorted(catalog.controls.items())
        if profile.system_type in c.applies_to and tier_applies(c.tier, level)
    ]
