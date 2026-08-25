"""API-key hashing. Keys are high-entropy random tokens, stored only as SHA-256 digests."""

import hashlib


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
