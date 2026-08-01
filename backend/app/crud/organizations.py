"""Organization repository: tenants, memberships and invites."""

import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.orgs import slugify
from app.models import (
    INVITE_PENDING,
    ORG_ROLE_OWNER,
    Organization,
    OrganizationInvite,
    OrganizationMember,
    User,
)

INVITE_TOKEN_EXPIRE_DAYS = 7


async def get_organization(
    session: AsyncSession, organization_id: Any
) -> Organization | None:
    return await session.get(Organization, organization_id)


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


async def list_user_memberships(
    session: AsyncSession, user_id: Any
) -> Sequence[OrganizationMember]:
    return (
        await session.exec(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == user_id)
            .order_by(col(OrganizationMember.created_at).desc())
        )
    ).all()


async def create_organization(
    session: AsyncSession, *, name: str, user: User
) -> Organization:
    base_slug = slugify(name)
    slug = base_slug
    counter = 1
    while (
        await session.exec(select(Organization).where(Organization.slug == slug))
    ).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    org = Organization(name=name, slug=slug)
    session.add(org)
    await session.flush()
    session.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role=ORG_ROLE_OWNER)
    )
    return org


async def update_organization(
    session: AsyncSession, organization: Organization, *, name: str | None = None
) -> Organization:
    if name is not None:
        organization.name = name
    session.add(organization)
    return organization


async def list_members(
    session: AsyncSession, organization_id: Any
) -> Sequence[OrganizationMember]:
    return (
        await session.exec(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(col(OrganizationMember.created_at))
        )
    ).all()


async def add_member(
    session: AsyncSession,
    *,
    organization_id: Any,
    user_id: Any,
    role: str,
) -> OrganizationMember:
    member = OrganizationMember(
        organization_id=organization_id, user_id=user_id, role=role
    )
    session.add(member)
    return member


async def update_member_role(
    session: AsyncSession,
    *,
    organization_id: Any,
    user_id: Any,
    role: str,
) -> OrganizationMember | None:
    member = (
        await session.exec(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
    ).first()
    if member is not None:
        member.role = role
        session.add(member)
    return member


async def remove_member(
    session: AsyncSession, *, organization_id: Any, user_id: Any
) -> OrganizationMember | None:
    member = (
        await session.exec(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
    ).first()
    if member is not None:
        await session.delete(member)
    return member


async def count_members(session: AsyncSession, organization_id: Any) -> int:
    """Count ACTIVE memberships (SCIM-deactivated members don't consume seats)."""
    members = await list_members(session, organization_id)
    return len([m for m in members if m.active])


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def invite_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=INVITE_TOKEN_EXPIRE_DAYS)


async def create_invite(
    session: AsyncSession,
    *,
    organization_id: Any,
    email: str,
    role: str,
    invited_by: User,
) -> OrganizationInvite:
    invite = OrganizationInvite(
        organization_id=organization_id,
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


async def get_invite_by_token(
    session: AsyncSession, token: str
) -> OrganizationInvite | None:
    return (
        await session.exec(
            select(OrganizationInvite).where(OrganizationInvite.token == token)
        )
    ).first()


async def get_pending_invite(
    session: AsyncSession, *, organization_id: Any, email: str
) -> OrganizationInvite | None:
    return (
        await session.exec(
            select(OrganizationInvite).where(
                OrganizationInvite.organization_id == organization_id,
                OrganizationInvite.email == email,
                OrganizationInvite.status == INVITE_PENDING,
            )
        )
    ).first()


async def list_invites(
    session: AsyncSession, organization_id: Any
) -> Sequence[OrganizationInvite]:
    return (
        await session.exec(
            select(OrganizationInvite)
            .where(OrganizationInvite.organization_id == organization_id)
            .order_by(col(OrganizationInvite.created_at).desc())
        )
    ).all()
