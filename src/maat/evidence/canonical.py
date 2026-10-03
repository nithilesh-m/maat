from __future__ import annotations

import hashlib
from typing import Any

import rfc8785


def canonical_json(obj: Any) -> bytes:
    """RFC 8785 (JCS) canonical JSON bytes."""
    return rfc8785.dumps(obj)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(obj: Any) -> str:
    return "sha256:" + sha256_hex(canonical_json(obj))
