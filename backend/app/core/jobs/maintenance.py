"""Scheduled maintenance jobs (ARQ cron)."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import col, select

from app.core.db import async_session_factory
from app.models import (
    INVITE_EXPIRED,
    INVITE_PENDING,
    ORG_ROLE_OWNER,
    OrganizationInvite,
    OrganizationMember,
    Session,
    Subscription,
    User,
)

logger = logging.getLogger(__name__)


async def cleanup_expired_invites_job(_ctx: dict[str, Any]) -> None:
    """Mark expired organization invites as expired."""
    async with async_session_factory() as session:
        invites = (
            await session.exec(
                select(OrganizationInvite).where(
                    OrganizationInvite.status == INVITE_PENDING,
                    OrganizationInvite.expires_at != None,  # noqa: E711
                )
            )
        ).all()
        now = datetime.now(UTC)
        for invite in invites:
            if invite.expires_at is not None and invite.expires_at < now:
                invite.status = INVITE_EXPIRED
                session.add(invite)
        await session.commit()
        logger.info("Cleaned up %d expired invites", len(invites))


async def cleanup_revoked_sessions_job(_ctx: dict[str, Any]) -> None:
    """Purge old auth sessions."""
    async with async_session_factory() as session:
        cutoff = datetime.now(UTC) - timedelta(days=30)
        stale = (
            await session.exec(select(Session).where(col(Session.created_at) < cutoff))
        ).all()
        for session_row in stale:
            await session.delete(session_row)
        await session.commit()
        logger.info("Purged %d stale sessions", len(stale))


async def subscription_dunning_job(_ctx: dict[str, Any]) -> None:
    """Email owners of past-due organizations."""
    async with async_session_factory() as session:
        subscriptions = (
            await session.exec(
                select(Subscription).where(Subscription.status == "past_due")
            )
        ).all()
        for subscription in subscriptions:
            if subscription.organization_id is None:
                continue
            owner_membership = (
                await session.exec(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id
                        == subscription.organization_id,
                        OrganizationMember.role == ORG_ROLE_OWNER,
                    )
                )
            ).first()
            if owner_membership:
                owner = await session.get(User, owner_membership.user_id)
                if owner and owner.email:
                    logger.info(
                        "Dunning email would be sent to %s (past due)",
                        owner.email,
                    )
        logger.info("Dunning check complete")
