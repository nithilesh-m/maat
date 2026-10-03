from __future__ import annotations

from pathlib import Path
from typing import Any

from maat.evidence.canonical import canonical_json, sha256_hex
from maat.schemas.evidence import ArtifactRef


class ArtifactIntegrityError(RuntimeError):
    pass


class ArtifactStore:
    def __init__(self, root: Path, run_id: str) -> None:
        self.root = Path(root)
        self.run_id = run_id
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, data: bytes, agent: str, name: str, sensitive: bool = False) -> ArtifactRef:
        hexd = sha256_hex(data)
        path = self.root / hexd
        if not path.exists():
            path.write_bytes(data)
        return ArtifactRef(
            uri=f"evidence://{self.run_id}/{agent}/{name}",
            sha256="sha256:" + hexd,
            sensitive=sensitive,
        )

    def put_json(self, obj: Any, agent: str, name: str, sensitive: bool = False) -> ArtifactRef:
        return self.put_bytes(canonical_json(obj), agent, name, sensitive)

    def get(self, ref_or_digest: ArtifactRef | str) -> bytes:
        d = ref_or_digest.sha256 if isinstance(ref_or_digest, ArtifactRef) else ref_or_digest
        hexd = d.removeprefix("sha256:")
        data = (self.root / hexd).read_bytes()  # FileNotFoundError propagates
        if sha256_hex(data) != hexd:
            raise ArtifactIntegrityError(f"artifact {d} content does not match its digest")
        return data
