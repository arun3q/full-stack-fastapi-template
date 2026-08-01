"""SCIM 2.0 provisioning endpoints.

Authenticated with an organization API key (``Authorization: Bearer`` or
``X-API-Key``). Users are provisioned as members of the key's organization;
groups map to membership roles (owner/admin/member/viewer).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.api_keys import parse_scopes
from app.crud.api_keys import find_by_key
from app.crud.organizations import (
    add_member,
    find_membership,
    get_organization,
    list_members,
)
from app.crud.users import create_user as create_user_record
from app.models import (
    ORG_ROLE_MEMBER,
    ApiKey,
    Organization,
    OrganizationMember,
    User,
    UserCreate,
)

router = APIRouter(prefix="/scim/v2", tags=["scim"])

ROLE_GROUP_IDS = {
    "owner": "group-owner",
    "admin": "group-admin",
    "member": "group-member",
    "viewer": "group-viewer",
}
GROUP_IDS_ROLES = {v: k for k, v in ROLE_GROUP_IDS.items()}


class ScimName(BaseModel):
    formatted: str | None = None
    givenName: str | None = None
    familyName: str | None = None


class ScimEmail(BaseModel):
    value: str
    primary: bool = True


class ScimUserRequest(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    userName: EmailStr
    displayName: str | None = None
    name: ScimName | None = None
    active: bool = True


class ScimPatchOperation(BaseModel):
    op: str = "replace"
    path: str | None = None
    value: Any = None


class ScimPatchRequest(BaseModel):
    schemas: list[str] = ["urn:ietf:params:scim:api:messages:2.0:PatchOp"]
    active: bool | None = None
    displayName: str | None = None
    name: ScimName | None = None
    Operations: list[ScimPatchOperation] | None = None


async def get_scim_context(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> tuple[ApiKey, Organization]:
    key = (authorization or "").removeprefix("Bearer ").strip() or x_api_key
    if not key:
        raise HTTPException(status_code=401, detail="SCIM token required")
    api_key = await find_by_key(session, key)
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid SCIM token")
    # SCIM provisioning requires an API key explicitly scoped for it
    scopes = set(parse_scopes(api_key.scopes))
    if "scim" not in scopes and "*" not in scopes:
        raise HTTPException(
            status_code=403, detail="API key does not have the scim scope"
        )
    org = await get_organization(session, api_key.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if not org.is_active:
        raise HTTPException(status_code=403, detail="Organization is suspended")
    return api_key, org


ScimContext = Annotated[tuple[ApiKey, Organization], Depends(get_scim_context)]


def _user_resource(user: User, membership: OrganizationMember) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": str(user.id),
        "userName": str(user.email),
        "displayName": user.full_name,
        "active": membership.active,
        "name": {"formatted": user.full_name},
        "emails": [{"value": str(user.email), "primary": True}],
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat() if user.created_at else None,
            "lastModified": user.created_at.isoformat() if user.created_at else None,
        },
        "x-role": membership.role,
    }


@router.get("/ServiceProviderConfig")
async def service_provider_config() -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True},
        "bulk": {"supported": False},
        "filter": {"supported": False},
        "authenticationSchemes": [{"name": "Bearer Auth", "type": "oauthbearertoken"}],
    }


@router.get("/Users")
async def list_scim_users(
    session: SessionDep,
    ctx: ScimContext,
    startIndex: int = 1,
    count: int = 100,
) -> dict[str, Any]:
    _, org = ctx
    memberships = await list_members(session, org.id)
    resources = []
    for membership in memberships:
        user = await session.get(User, membership.user_id)
        if user is not None:
            resources.append(_user_resource(user, membership))
    start = max(0, startIndex - 1)
    page = resources[start : start + count]
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(resources),
        "itemsPerPage": len(page),
        "startIndex": startIndex,
        "Resources": page,
    }


@router.get("/Users/{user_id}")
async def get_scim_user(
    session: SessionDep, ctx: ScimContext, user_id: str
) -> dict[str, Any]:
    _, org = ctx
    membership = await find_membership(session, organization_id=org.id, user_id=user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="User not found")
    user = await session.get(User, membership.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_resource(user, membership)


@router.post("/Users", status_code=201)
async def create_scim_user(
    session: SessionDep, ctx: ScimContext, body: ScimUserRequest
) -> dict[str, Any]:
    """Provision a user into the token's organization."""
    _, org = ctx
    existing = (
        await session.exec(select(User).where(User.email == str(body.userName)))
    ).first()
    if existing:
        membership = await find_membership(
            session, organization_id=org.id, user_id=existing.id
        )
        if membership is not None:
            raise HTTPException(status_code=409, detail="User already exists")
        membership = await add_member(
            session, organization_id=org.id, user_id=existing.id, role=ORG_ROLE_MEMBER
        )
        await session.commit()
        return _user_resource(existing, membership)

    full_name = body.displayName or (body.name.formatted if body.name else None)
    user = await create_user_record(
        session=session,
        user_create=UserCreate(
            email=str(body.userName),
            full_name=full_name,
            is_active=body.active,
        ),
    )
    membership = await add_member(
        session, organization_id=org.id, user_id=user.id, role=ORG_ROLE_MEMBER
    )
    await session.commit()
    return _user_resource(user, membership)


@router.patch("/Users/{user_id}")
async def patch_scim_user(
    session: SessionDep, ctx: ScimContext, user_id: str, body: ScimPatchRequest
) -> dict[str, Any]:
    """Update a user (deactivation sets ``active=false``)."""
    _, org = ctx
    membership = await find_membership(session, organization_id=org.id, user_id=user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="User not found")
    user = await session.get(User, membership.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if body.active is not None:
        membership.active = body.active
    if body.displayName is not None:
        user.full_name = body.displayName
    # SCIM 2.0 Operations[] PatchOp (e.g. [{"op":"replace","path":"active","value":false}])
    for operation in body.Operations or []:
        path = (operation.path or "").lower()
        value = operation.value
        if "active" in path:
            membership.active = bool(value)
        elif "displayname" in path or "name" in path:
            if isinstance(value, str):
                user.full_name = value
        elif path in ("username", "userName", "emails", "email"):
            raise HTTPException(
                status_code=400,
                detail="Changing userName/email via SCIM is not supported",
            )
        # unknown paths are ignored (SCIM allows best-effort)
    session.add(membership)
    session.add(user)
    await session.commit()
    return _user_resource(user, membership)


@router.delete("/Users/{user_id}", status_code=204)
async def delete_scim_user(session: SessionDep, ctx: ScimContext, user_id: str) -> None:
    """Deactivate a user (SCIM delete == deactivate)."""
    _, org = ctx
    membership = await find_membership(session, organization_id=org.id, user_id=user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="User not found")
    # SCIM delete == deactivate, scoped to THIS membership only
    membership.active = False
    session.add(membership)
    await session.commit()


@router.get("/Groups")
async def list_scim_groups(session: SessionDep, ctx: ScimContext) -> dict[str, Any]:
    """List groups (each membership role is a group)."""
    _, org = ctx
    memberships = await list_members(session, org.id)
    resources = []
    for role, group_id in ROLE_GROUP_IDS.items():
        members = [
            {"value": str(m.user_id), "display": str(m.user_id)}
            for m in memberships
            if m.role == role
        ]
        resources.append(
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": group_id,
                "displayName": role,
                "members": members,
            }
        )
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(resources),
        "Resources": resources,
    }
