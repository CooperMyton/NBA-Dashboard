"""Admin CLI to mint an API key for POST /model/predict (docs/decisions.md D-007).

There is no public registration: an operator runs this to create a key. The plaintext key is
shown once; only its SHA-256 digest is stored.

Usage: ``python -m backend.scripts.mint_api_key --name "my client"``
"""

import argparse
import asyncio
import secrets

from backend.app.core.security import hash_api_key
from backend.app.db.session import SessionLocal
from backend.app.models.user import User


async def mint(name: str) -> str:
    key = secrets.token_urlsafe(32)
    async with SessionLocal() as session:
        session.add(User(name=name, api_key_hash=hash_api_key(key), is_active=True))
        await session.commit()
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description="Mint an API key for POST /model/predict.")
    parser.add_argument("--name", required=True, help="Human label for the key's owner")
    args = parser.parse_args()
    key = asyncio.run(mint(args.name))
    print(f"API key for {args.name!r} (store securely — shown only once):\n{key}")


if __name__ == "__main__":
    main()
