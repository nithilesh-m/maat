from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class ApiSettings(BaseModel):
    runs_dir: Path = Path("runs")
    users_file: Path = Path("api_users.toml")
    maat_config: Path = Path("maat.toml")
    reviewer_key: Path = Path("~/.maat/reviewer.pem").expanduser()
    allow_origins: list[str] = ["http://localhost:3000"]
    data_root: Path = Path(".")  # profiles may only reference files under this directory
    allow_same_family_judges: bool = False  # operator ablation switch (demo / single-model setups)
    screen: Literal["prompt_guard", "none"] = "prompt_guard"  # "none" is an operator ablation
    allowed_auth_env: list[str] = []  # env-var names a profile may use as `target.auth_env`

    @classmethod
    def from_env(cls) -> ApiSettings:
        """Read MAAT_API_<FIELD> environment variables (list fields are comma-separated)."""
        values: dict = {}
        for name in cls.model_fields:
            raw = os.environ.get(f"MAAT_API_{name.upper()}")
            if raw is None:
                continue
            is_list = name in ("allow_origins", "allowed_auth_env")
            values[name] = [o.strip() for o in raw.split(",") if o.strip()] if is_list else raw
        return cls(**values)
