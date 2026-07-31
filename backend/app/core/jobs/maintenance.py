"""Scheduled maintenance jobs (ARQ cron)."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import col, select

from app.core.config import settings
from app.core.db import async_session_factory
from app.core.jobs.base import enqueue_job
from app.core.jobs.emails import send_email_background
from app.core.jobs.webhooks import MAX_WEBHOOK_ATTEMPTS
from app.core.notifications import notify
from app.models import (
    INVITE_EXPIRED,
    INVITE_PENDING,
    ORG_ROLE_OWNER,
    OrganizationInvite,
    OrganizationMember,
    Session,
    Subscription,
    User,
    WebhookDelivery,
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
        expired: list[OrganizationInvite] = []
        for invite in invites:
            if invite.expires_at is not None and invite.expires_at < now:
                invite.status = INVITE_EXPIRED
                session.add(invite)
                expired.append(invite)
        await session.commit()
        logger.info("Cleaned up %d expired invites", len(expired))


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
    """Email owners of past-due organizations (daily)."""
    from app.models import Organization
    from app.utils import generate_dunning_email

    async with async_session_factory() as session:
        subscriptions = (
            await session.exec(
                select(Subscription).where(Subscription.status == "past_due")
            )
        ).all()
        sent = 0
        for subscription in subscriptions:
            if subscription.organization_id is None:
                continue
            org = await session.get(Organization, subscription.organization_id)
            owner_membership = (
                await session.exec(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id
                        == subscription.organization_id,
                        OrganizationMember.role == ORG_ROLE_OWNER,
                    )
                )
            ).first()
            if owner_membership is None or org is None:
                continue
            owner = await session.get(User, owner_membership.user_id)
            if owner is None or not owner.email:
                continue
            email_data = generate_dunning_email(
                org_name=org.name,
                owner_name=owner.full_name or str(owner.email),
                billing_url=f"{settings.FRONTEND_HOST}/billing",
            )
            await send_email_background(
                email_to=str(owner.email),
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
            await notify(
                session,
                user_id=owner.id,
                type="billing",
                title="Payment past due",
                body=(
                    f"Update your payment method for {org.name} "
                    "to avoid an interruption."
                ),
            )
            sent += 1
        await session.commit()
        logger.info("Dunning check complete: %d reminder(s) sent", sent)


async def requeue_stale_webhook_deliveries_job(_ctx: dict[str, Any]) -> None:
    """Re-queue pending webhook deliveries whose retry window has passed.

    Only targets deliveries that were already attempted (``attempts > 0``) and
    have a scheduled ``next_retry_at`` in the past. Brand-new deliveries are
    excluded (they were already enqueued by ``dispatch_webhooks``), which avoids
    duplicate POSTs to customer endpoints.
    """
    async with async_session_factory() as session:
        now = datetime.now(UTC)
        stale = (
            await session.exec(
                select(WebhookDelivery).where(
                    WebhookDelivery.status == "pending",
                    WebhookDelivery.attempts > 0,
                    WebhookDelivery.attempts < MAX_WEBHOOK_ATTEMPTS,
                    col(WebhookDelivery.next_retry_at).is_not(None),
                    col(WebhookDelivery.next_retry_at) < now,
                )
            )
        ).all()
        requeued = 0
        for delivery in stale:
            # Bump the retry time so a queued job isn't re-picked on the next tick
            delivery.next_retry_at = now + timedelta(minutes=5)
            session.add(delivery)
            await enqueue_job(
                "deliver_webhook_job",
                delivery_id=str(delivery.id),
                attempt=delivery.attempts + 1,
            )
            requeued += 1
        await session.commit()
        logger.info("Re-queued %d stale webhook deliveries", requeued)
