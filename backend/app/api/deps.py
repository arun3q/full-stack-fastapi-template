import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.access import billing_enabled, get_active_plan, is_admin, is_staff
from app.core.config import settings
from app.core.db import async_session_factory
from app.models import TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(session: SessionDep, token: TokenDep) -> User:
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


async def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not is_admin(current_user):
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def require_roles(*roles: str) -> Callable[..., Awaitable[User]]:
    """Require the current user to hold one of the given roles.

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


def require_plan(*plan_slugs: str) -> Callable[..., Awaitable[User]]:
    """Require the current user to hold an active subscription to a plan.

    Admins/staff always pass. When no payment provider is configured the gate
    is disabled (``require_plan`` passes for everyone). Example:
    ``require_plan("pro", "business", "enterprise")``.
    """

    async def _dependency(session: SessionDep, current_user: CurrentUser) -> User:
        if not billing_enabled() or is_staff(current_user):
            return current_user
        plan = await get_active_plan(session, current_user.id)
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
