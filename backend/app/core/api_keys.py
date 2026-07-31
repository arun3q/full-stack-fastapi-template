"""API keys / service accounts: generation and hashing (pure helpers).

Persistence lives in ``app.crud.api_keys``. Keys are hashed with HMAC-SHA256
keyed by the server's ``SECRET_KEY`` (pepper) so a database leak doesn't enable
offline brute force.
"""

import hashlib
import hmac
import json
import secrets
from typing import Any

from app.core.config import settings

API_KEY_PREFIX = "sk_"


def generate_api_key() -> tuple[str, str]:
    """Return ``(plaintext_key, key_hash)``. The plaintext is only shown once."""
    plaintext = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    return plaintext, hash_api_key(plaintext)


def hash_api_key(key: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), key.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def parse_scopes(raw: str) -> list[str]:
    try:
        parsed: Any = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []
