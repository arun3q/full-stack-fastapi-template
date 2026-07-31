from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import CurrentOrg, SessionDep, require_org_permission
from app.core.api_keys import parse_scopes
from app.crud.api_keys import (
    create_api_key as create_key,
)
from app.crud.api_keys import (
    find_by_key,
    get_api_key,
    list_api_keys,
    revoke_api_key,
)
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


@router.get(
    "/",
    dependencies=[Depends(require_org_permission("org:view"))],
    response_model=ApiKeysPublic,
)
async def read_api_keys(session: SessionDep, current_org: CurrentOrg) -> Any:
    """List the active organization's API keys."""
    keys = await list_api_keys(session, current_org.id)
    return {
        "data": [_to_public(k) for k in keys],
        "count": len(keys),
    }


@router.post(
    "/",
    dependencies=[Depends(require_org_permission("billing:manage"))],
    response_model=ApiKeyCreated,
)
async def create_api_key_route(
    *, session: SessionDep, current_org: CurrentOrg, body: ApiKeyCreate
) -> Any:
    """Create an API key. The plaintext key is only shown once."""
    api_key, plaintext = await create_key(
        session,
        organization_id=current_org.id,
        name=body.name,
        scopes=body.scopes,
    )
    await session.commit()
    await session.refresh(api_key)
    public = _to_public(api_key)
    return ApiKeyCreated(**public.model_dump(), key=plaintext)


@router.delete(
    "/{key_id}",
    dependencies=[Depends(require_org_permission("billing:manage"))],
    response_model=Message,
)
async def revoke_api_key_route(
    session: SessionDep, current_org: CurrentOrg, key_id: Any
) -> Message:
    """Revoke an API key."""
    from uuid import UUID

    try:
        key_uuid = UUID(str(key_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key = await get_api_key(session, key_uuid)
    if api_key is None or api_key.organization_id != current_org.id:
        raise HTTPException(status_code=404, detail="API key not found")
    await revoke_api_key(session, api_key)
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
    api_key = await find_by_key(session, x_api_key)
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    api_key.last_used_at = datetime.now(UTC)
    session.add(api_key)
    await session.commit()
    return api_key


ApiKeyDep = Annotated[ApiKey, Depends(authenticate_api_key)]


@router.get("/me")
async def read_api_key_me(session: SessionDep, api_key: ApiKeyDep) -> dict[str, Any]:
    """Demo endpoint authenticated via X-API-Key (returns key + org info)."""
    org = await session.get(Organization, api_key.organization_id)
    return {
        "name": api_key.name,
        "scopes": parse_scopes(api_key.scopes),
        "organization": org.name if org else None,
    }
