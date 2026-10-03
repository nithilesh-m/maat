from __future__ import annotations

import base64
import binascii
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_PREFIX = "ed25519:"


class RunKey:
    """Ed25519 signing key for a run (or a reviewer)."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._sk = private_key

    @classmethod
    def generate(cls) -> RunKey:
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_seed(cls, seed: bytes) -> RunKey:
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    @classmethod
    def load_pem(cls, path: Path) -> RunKey:
        sk = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
        if not isinstance(sk, Ed25519PrivateKey):
            raise ValueError(f"{path} is not an Ed25519 private key")
        return cls(sk)

    def save_pem(self, path: Path) -> None:
        pem = self._sk.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        Path(path).write_bytes(pem)

    @property
    def public_key_b64(self) -> str:
        raw = self._sk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return base64.b64encode(raw).decode()

    def sign(self, data: bytes) -> str:
        return _PREFIX + base64.b64encode(self._sk.sign(data)).decode()


def verify_signature(public_key_b64: str, data: bytes, sig: str) -> bool:
    if not sig.startswith(_PREFIX):
        return False
    try:
        pk = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
        pk.verify(base64.b64decode(sig[len(_PREFIX) :], validate=True), data)
        return True
    except (InvalidSignature, ValueError, binascii.Error):
        return False
