"""Organization / tenant helpers: personal workspaces, roles and permissions."""

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import (
    INVITE_PENDING,
    ORG_ROLE_ADMIN,
    ORG_ROLE_MEMBER,
    ORG_ROLE_OWNER,
    ORG_ROLE_VIEWER,
    Organization,
    OrganizationInvite,
    OrganizationMember,
    User,
)

INVITE_TOKEN_EXPIRE_DAYS = 7

# Per-tenant role -> permissions
ORG_ROLE_PERMISSIONS: dict[str, set[str]] = {
    ORG_ROLE_OWNER: {
        "org:view",
        "org:update",
        "org:delete",
        "member:invite",
        "member:manage",
        "member:remove",
        "billing:manage",
        "item:create",
        "item:read",
        "item:update",
        "item:delete",
    },
    ORG_ROLE_ADMIN: {
        "org:view",
        "org:update",
        "member:invite",
        "member:manage",
        "billing:manage",
        "item:create",
        "item:read",
        "item:update",
        "item:delete",
    },
    ORG_ROLE_MEMBER: {
        "org:view",
        "item:create",
        "item:read",
        "item:update",
    },
    ORG_ROLE_VIEWER: {
        "org:view",
        "item:read",
    },
}

ROLE_RANK = {
    ORG_ROLE_VIEWER: 1,
    ORG_ROLE_MEMBER: 2,
    ORG_ROLE_ADMIN: 3,
    ORG_ROLE_OWNER: 4,
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "org"


def has_permission(role: str, permission: str) -> bool:
    return permission in ORG_ROLE_PERMISSIONS.get(role, set())


async def find_membership(
    session: AsyncSession, *, organization_id: Any, user_id: Any
) -> OrganizationMember | None:
    return (
        await session.exec(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
    ).first()


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

    name = user.full_name or user.email or "My Workspace"
    org = Organization(name=name, slug=f"personal-{uuid.uuid4().hex[:12]}")
    session.add(org)
    await session.flush()
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=ORG_ROLE_OWNER,
    )
    session.add(member)
    await session.flush()
    return org


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def invite_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=INVITE_TOKEN_EXPIRE_DAYS)


async def create_organization_invite(
    session: AsyncSession,
    *,
    organization: Organization,
    email: str,
    role: str,
    invited_by: User,
) -> OrganizationInvite:
    invite = OrganizationInvite(
        organization_id=organization.id,
        email=email,
        role=role,
        token=generate_invite_token(),
        invited_by=invited_by.id,
        status=INVITE_PENDING,
        expires_at=invite_expiry(),
    )
    session.add(invite)
    await session.flush()
    return invite


async def count_members(session: AsyncSession, organization_id: Any) -> int:
    return len(
        (
            await session.exec(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == organization_id
                )
            )
        ).all()
    )


def max_seats_for_plan(quotas: str | None) -> int:
    """Resolve the seat quota from a plan's JSON quotas string (0 = unlimited)."""
    import json

    if not quotas:
        return 0
    try:
        parsed: dict[str, Any] = json.loads(quotas)
        value = parsed.get("max_seats", 0)
        return int(value) if isinstance(value, (int, float)) else 0
    except Exception:
        return 0


def max_items_for_plan(quotas: str | None) -> int:
    """Resolve the item quota from a plan's JSON quotas string (0 = unlimited)."""
    import json

    if not quotas:
        return 0
    try:
        parsed: dict[str, Any] = json.loads(quotas)
        value = parsed.get("max_items", 0)
        return int(value) if isinstance(value, (int, float)) else 0
    except Exception:
        return 0
