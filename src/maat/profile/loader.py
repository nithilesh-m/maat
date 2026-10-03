from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from maat.schemas.profile import SystemProfile


class ProfileError(ValueError):
    """Raised when a system profile cannot be loaded or validated."""


def _describe(err: ValidationError) -> str:
    parts = []
    for e in err.errors(include_input=False, include_url=False):
        loc = ".".join(str(x) for x in e["loc"])
        parts.append(f"{loc}: {e['msg']} ({e['type']})")
    return "; ".join(parts)


def load_profile(path: Path) -> SystemProfile:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ProfileError(f"profile not found: {path}") from e
    except yaml.YAMLError as e:
        raise ProfileError(f"invalid YAML in {path}: {e}") from e
    if not isinstance(raw, dict):
        raise ProfileError(f"{path}: expected a mapping at top level")
    try:
        return SystemProfile.model_validate(raw)
    except ValidationError as e:
        raise ProfileError(f"{path}: {_describe(e)}") from None
