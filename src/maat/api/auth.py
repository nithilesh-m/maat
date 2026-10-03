from __future__ import annotations

import hashlib
import tomllib
from enum import IntEnum
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel


class Role(IntEnum):
    viewer = 1
    reviewer = 2
    admin = 3


class User(BaseModel):
    name: str
    role: Role


def load_users(path: Path) -> dict[str, User]:
    if not Path(path).exists():
        return {}
    data = tomllib.loads(Path(path).read_text())
    return {
        u["token_sha256"]: User(name=u["name"], role=Role[u["role"]]) for u in data.get("users", [])
    }


def require(min_role: Role):
    def dep(request: Request) -> User:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        user = request.app.state.users.get(hashlib.sha256(auth[7:].encode()).hexdigest())
        if user is None:
            raise HTTPException(401, "invalid token")
        if user.role < min_role:
            raise HTTPException(403, f"requires role {min_role.name}")
        return user

    return Depends(dep)
