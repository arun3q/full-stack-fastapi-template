"""API key repository."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.api_keys import generate_api_key, hash_api_key
from app.models import ApiKey


async def find_by_key(session: AsyncSession, key: str) -> ApiKey | None:
    return (
        await session.exec(
            select(ApiKey).where(
                ApiKey.key_hash == hash_api_key(key),
                col(ApiKey.revoked_at).is_(None),
            )
        )
    ).first()


async def create_api_key(
    session: AsyncSession,
    *,
    organization_id: Any,
    name: str,
    scopes: list[str],
) -> tuple[ApiKey, str]:
    import json

    plaintext, key_hash = generate_api_key()
    api_key = ApiKey(
        organization_id=organization_id,
        name=name,
        key_hash=key_hash,
        scopes=json.dumps(scopes or ["read"]),
    )
    session.add(api_key)
    await session.flush()
    return api_key, plaintext


async def list_api_keys(
    session: AsyncSession, organization_id: Any
) -> Sequence[ApiKey]:
    return (
        await session.exec(
            select(ApiKey)
            .where(
                ApiKey.organization_id == organization_id,
                col(ApiKey.revoked_at).is_(None),
            )
            .order_by(col(ApiKey.created_at).desc())
        )
    ).all()


async def get_api_key(session: AsyncSession, key_id: Any) -> ApiKey | None:
    return await session.get(ApiKey, key_id)


async def revoke_api_key(session: AsyncSession, api_key: ApiKey) -> None:
    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.now(UTC)
        session.add(api_key)
