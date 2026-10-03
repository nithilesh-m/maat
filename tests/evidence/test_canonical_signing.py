from hypothesis import given
from hypothesis import strategies as st

from maat.evidence.canonical import canonical_json, digest, sha256_hex
from maat.evidence.signing import RunKey, verify_signature

SEED = b"\x01" * 32


def test_canonical_json_is_key_order_independent():
    assert canonical_json({"b": 1, "a": [1, 2]}) == canonical_json({"a": [1, 2], "b": 1})


def test_digest_format():
    d = digest({"x": 1})
    assert d.startswith("sha256:") and len(d) == len("sha256:") + 64


def test_sha256_hex_known_value():
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


@given(st.dictionaries(st.text(), st.integers(-(2**53 - 1), 2**53 - 1) | st.text() | st.booleans()))
def test_digest_stable_for_same_object(obj):
    assert digest(obj) == digest(dict(reversed(list(obj.items()))))


def test_sign_and_verify_roundtrip():
    key = RunKey.from_seed(SEED)
    sig = key.sign(b"hello")
    assert sig.startswith("ed25519:")
    assert verify_signature(key.public_key_b64, b"hello", sig)
    assert not verify_signature(key.public_key_b64, b"hellO", sig)


def test_signing_is_deterministic_for_same_key():
    assert RunKey.from_seed(SEED).sign(b"x") == RunKey.from_seed(SEED).sign(b"x")


def test_verify_rejects_garbage_without_raising():
    key = RunKey.from_seed(SEED)
    assert not verify_signature(key.public_key_b64, b"x", "ed25519:!!!notbase64")
    assert not verify_signature(key.public_key_b64, b"x", "rsa:abc")
    assert not verify_signature("not-a-key", b"x", key.sign(b"x"))


def test_pem_roundtrip(tmp_path):
    key = RunKey.generate()
    key.save_pem(tmp_path / "k.pem")
    again = RunKey.load_pem(tmp_path / "k.pem")
    assert again.public_key_b64 == key.public_key_b64
