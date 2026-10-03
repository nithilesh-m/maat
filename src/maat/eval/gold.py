from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class GoldItem(BaseModel):
    id: str
    control_id: str
    dossier_docs: list[str] = Field(default_factory=list)
    text: str | None = None
    label: Literal["S", "P", "N", "NA"]
    span: str | None = None
    source: str


def load_gold(path: Path) -> list[GoldItem]:
    return [
        GoldItem.model_validate_json(line)
        for line in Path(path).read_text().splitlines()
        if line.strip()
    ]
