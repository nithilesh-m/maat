import pytest

from maat.evidence.artifacts import ArtifactIntegrityError, ArtifactStore


def test_put_json_is_content_addressed(tmp_path):
    store = ArtifactStore(tmp_path / "artifacts", "run-1")
    a = store.put_json({"b": 1, "a": 2}, "risk", "out.json")
    b = store.put_json({"a": 2, "b": 1}, "risk", "out.json")
    assert a.sha256 == b.sha256 and a.sha256.startswith("sha256:")
    assert a.uri == "evidence://run-1/risk/out.json"
    assert store.get(a) == store.get(a.sha256)


def test_sensitive_flag_kept(tmp_path):
    ref = ArtifactStore(tmp_path, "r").put_bytes(b"x", "risk", "x.txt", sensitive=True)
    assert ref.sensitive is True


def test_missing_artifact(tmp_path):
    with pytest.raises(FileNotFoundError):
        ArtifactStore(tmp_path, "r").get("sha256:" + "0" * 64)


def test_tampered_artifact_detected(tmp_path):
    store = ArtifactStore(tmp_path, "r")
    ref = store.put_bytes(b"original", "risk", "x.txt")
    (tmp_path / ref.sha256.removeprefix("sha256:")).write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError):
        store.get(ref)
