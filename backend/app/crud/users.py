"""User repository: persistence for user accounts and auth."""

import uuid
from collections.abc import Sequence

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models import (
    ORG_ROLE_OWNER,
    Organization,
    OrganizationMember,
    User,
    UserCreate,
    UserUpdate,
)


async def create_user(*, session: AsyncSession, user_create: UserCreate) -> User:
    extra: dict[str, str | None] = {}
    if user_create.password:
        extra["hashed_password"] = get_password_hash(user_create.password)
    else:
        extra["hashed_password"] = None
    db_obj = User.model_validate(user_create, update=extra)
    session.add(db_obj)
    await session.flush()
    # Every user gets a personal organization (tenant) out of the box
    await ensure_personal_organization(session, db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def update_user(
    *, session: AsyncSession, db_user: User, user_in: UserUpdate
) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data and user_data["password"] is not None:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def get_user_by_email(*, session: AsyncSession, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    result = await session.exec(statement)
    return result.first()


async def get_user_by_id(*, session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def list_users(
    *, session: AsyncSession, skip: int = 0, limit: int = 100
) -> Sequence[User]:
    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    return (await session.exec(statement)).all()


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


async def authenticate(
    *, session: AsyncSession, email: str, password: str
) -> User | None:
    db_user = await get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(
        password, db_user.hashed_password or ""
    )
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)
    return db_user


async def ensure_personal_organization(
    session: AsyncSession, user: User
) -> Organization:
    """Create a private organization for a user if they don't have one."""
    existing = (
        await session.exec(
            select(OrganizationMember)
            .where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.role == ORG_ROLE_OWNER,
            )
            .order_by(col(OrganizationMember.created_at))
        )
    ).first()
    if existing:
        org = await session.get(Organization, existing.organization_id)
        if org is not None:
            return org

    org = Organization(
        name=user.full_name or user.email or "My Workspace",
        slug=f"personal-{uuid.uuid4().hex[:12]}",
    )
    session.add(org)
    await session.flush()
    session.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=ORG_ROLE_OWNER,
        )
    )
    await session.flush()
    return org
