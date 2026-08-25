"""Tests for API-key hashing."""

from backend.app.core.security import hash_api_key


def test_hash_is_deterministic_and_hides_the_key() -> None:
    digest = hash_api_key("secret-key")
    assert digest == hash_api_key("secret-key")
    assert digest != hash_api_key("other-key")
    assert "secret-key" not in digest
    assert len(digest) == 64  # sha-256 hex
