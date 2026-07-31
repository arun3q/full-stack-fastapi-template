import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.access import billing_enabled, get_active_plan, is_admin, is_staff
from app.core.config import settings
from app.core.db import async_session_factory, get_read_session, set_tenant_context
from app.core.orgs import has_permission
from app.crud.organizations import find_membership
from app.crud.users import ensure_personal_organization
from app.models import (
    Organization,
    OrganizationMember,
    TokenPayload,
    User,
)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)
optional_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]
ReadSessionDep = Annotated[AsyncSession, Depends(get_read_session)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(
    request: Request,
    session: SessionDep,
    token: Annotated[str | None, Depends(optional_oauth2)] = None,
) -> User:
    if not token and settings.AUTH_TOKEN_IN_COOKIE:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    if token_data.sub is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    try:
        user_id = uuid.UUID(token_data.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_organization(
    session: SessionDep,
    current_user: CurrentUser,
    request: Request,
) -> Organization:
    """Resolve the active tenant.

    Uses the ``X-Organization-ID`` header when provided (validated against the
    user's memberships), otherwise falls back to the user's most recent
    membership (their personal organization).
    """
    requested = request.headers.get("X-Organization-ID")
    membership: OrganizationMember | None = None
    if requested:
        try:
            org_uuid = uuid.UUID(requested)
        except ValueError:
            org_uuid = None
        if org_uuid is not None:
            membership = await find_membership(
                session, organization_id=org_uuid, user_id=current_user.id
            )
    if membership is None:
        membership = (
            await session.exec(
                select(OrganizationMember)
                .where(OrganizationMember.user_id == current_user.id)
                .order_by(col(OrganizationMember.created_at).desc())
            )
        ).first()
    if membership is None:
        created_org = await ensure_personal_organization(session, current_user)
        await session.commit()
        await set_tenant_context(
            session,
            organization_id=created_org.id,
            is_admin=is_staff(current_user),
        )
        return created_org
    active_org = await session.get(Organization, membership.organization_id)
    if active_org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if not active_org.is_active:
        raise HTTPException(status_code=403, detail="Organization is suspended")
    await set_tenant_context(
        session,
        organization_id=active_org.id,
        is_admin=is_staff(current_user),
    )
    return active_org


CurrentOrg = Annotated[Organization, Depends(get_current_organization)]


async def get_current_active_superuser(
    session: SessionDep, current_user: CurrentUser
) -> User:
    if not is_admin(current_user):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    # Under RLS, admins bypass tenant policies on cross-tenant reads
    await set_tenant_context(session, organization_id=None, is_admin=True)
    return current_user


def require_roles(*roles: str) -> Callable[..., Awaitable[User]]:
    """Require the current user to hold one of the given global roles.

    Admins and superusers always pass. Example: ``require_roles("staff")``.
    """

    async def _dependency(current_user: CurrentUser) -> User:
        if is_admin(current_user) or current_user.role in roles:
            return current_user
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have the required role",
        )

    return _dependency


def require_org_permission(permission: str) -> Callable[..., Awaitable[User]]:
    """Require the given permission on the active organization.

    Example: ``require_org_permission("member:invite")``.
    """

    async def _dependency(
        session: SessionDep,
        current_user: CurrentUser,
        current_org: CurrentOrg,
    ) -> User:
        membership = await find_membership(
            session, organization_id=current_org.id, user_id=current_user.id
        )
        role = membership.role if membership else ""
        if not has_permission(role, permission):
            raise HTTPException(
                status_code=403, detail=f"Missing permission: {permission}"
            )
        return current_user

    return _dependency


def require_plan(*plan_slugs: str) -> Callable[..., Awaitable[User]]:
    """Require the active organization to hold a subscription to a plan.

    Admins/staff always pass. When no payment provider is configured the gate
    is disabled (``require_plan`` passes for everyone). Example:
    ``require_plan("pro", "business", "enterprise")``.
    """

    async def _dependency(
        session: SessionDep,
        current_user: CurrentUser,
        current_org: CurrentOrg,
    ) -> User:
        if not billing_enabled() or is_staff(current_user):
            return current_user
        plan = await get_active_plan(session, current_org.id)
        if plan and plan.slug in plan_slugs:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This feature requires a "
                + ", ".join(slug.title() for slug in plan_slugs)
                + " plan"
            ),
        )

    return _dependency
