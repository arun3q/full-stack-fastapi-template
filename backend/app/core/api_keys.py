"""API keys / service accounts for programmatic access."""

import hashlib
import json
import secrets
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import ApiKey

API_KEY_PREFIX = "sk_"


def generate_api_key() -> tuple[str, str]:
    """Return ``(plaintext_key, key_hash)``. The plaintext is only shown once."""
    plaintext = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    return plaintext, hash_api_key(plaintext)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_scopes(raw: str) -> list[str]:
    try:
        parsed: Any = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


async def find_api_key(session: AsyncSession, key: str) -> ApiKey | None:
    return (
        await session.exec(
            select(ApiKey).where(
                ApiKey.key_hash == hash_api_key(key),
                col(ApiKey.revoked_at).is_(None),
            )
        )
    ).first()
