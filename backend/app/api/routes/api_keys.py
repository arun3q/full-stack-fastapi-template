import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import col, select

from app.api.deps import CurrentOrg, SessionDep
from app.core.api_keys import generate_api_key, parse_scopes
from app.models import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyPublic,
    ApiKeysPublic,
    Message,
    Organization,
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("/", response_model=ApiKeysPublic)
async def read_api_keys(session: SessionDep, current_org: CurrentOrg) -> Any:
    """List the active organization's API keys."""
    keys = (
        await session.exec(
            select(ApiKey)
            .where(
                ApiKey.organization_id == current_org.id,
                col(ApiKey.revoked_at).is_(None),
            )
            .order_by(col(ApiKey.created_at).desc())
        )
    ).all()
    return {
        "data": [_to_public(k) for k in keys],
        "count": len(keys),
    }


@router.post("/", response_model=ApiKeyCreated)
async def create_api_key(
    *, session: SessionDep, current_org: CurrentOrg, body: ApiKeyCreate
) -> Any:
    """Create an API key. The plaintext key is only shown once."""
    plaintext, key_hash = generate_api_key()
    api_key = ApiKey(
        organization_id=current_org.id,
        name=body.name,
        key_hash=key_hash,
        scopes=json.dumps(body.scopes or ["read"]),
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    public = _to_public(api_key)
    return ApiKeyCreated(**public.model_dump(), key=plaintext)


@router.delete("/{key_id}", response_model=Message)
async def revoke_api_key(
    session: SessionDep, current_org: CurrentOrg, key_id: Any
) -> Message:
    """Revoke an API key."""
    from uuid import UUID

    try:
        key_uuid = UUID(str(key_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key = await session.get(ApiKey, key_uuid)
    if api_key is None or api_key.organization_id != current_org.id:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.now(UTC)
        session.add(api_key)
        await session.commit()
    return Message(message="API key revoked")


def _to_public(api_key: ApiKey) -> ApiKeyPublic:
    return ApiKeyPublic(
        id=api_key.id,
        name=api_key.name,
        scopes=parse_scopes(api_key.scopes),
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
    )


async def authenticate_api_key(
    session: SessionDep,
    x_api_key: Annotated[str | None, Header()] = None,
) -> ApiKey:
    """Authenticate a request via ``X-API-Key``."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    from app.core.api_keys import find_api_key

    api_key = await find_api_key(session, x_api_key)
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    api_key.last_used_at = datetime.now(UTC)
    session.add(api_key)
    await session.commit()
    return api_key


ApiKeyDep = Annotated[ApiKey, Depends(authenticate_api_key)]


@router.get("/me", tags=["api"])
async def read_api_key_me(session: SessionDep, api_key: ApiKeyDep) -> dict[str, Any]:
    """Demo endpoint authenticated via X-API-Key (returns key + org info)."""
    org = await session.get(Organization, api_key.organization_id)
    return {
        "name": api_key.name,
        "scopes": parse_scopes(api_key.scopes),
        "organization": org.name if org else None,
    }
