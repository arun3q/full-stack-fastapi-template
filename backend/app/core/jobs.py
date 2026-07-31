"""Background job queue based on ARQ (backed by Redis).

Jobs are enqueued from request handlers and executed by a separate worker
process (see ``app/worker.py``). If Redis is unavailable the application keeps
working: enqueues fail gracefully and e.g. emails are sent inline as a fallback.
"""

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from sqlmodel import col, select

from app.core.config import settings
from app.core.db import async_session_factory
from app.models import PaymentEvent
from app.utils import send_email

logger = logging.getLogger(__name__)

_redis_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    parts = urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=parts.hostname or "localhost",
        port=parts.port or 6379,
        database=int((parts.path or "/0").lstrip("/") or 0),
        username=parts.username,
        password=parts.password,
        ssl=parts.scheme == "rediss",
    )


def set_redis_pool(pool: ArqRedis | None) -> None:
    global _redis_pool
    _redis_pool = pool


def get_redis_pool() -> ArqRedis | None:
    return _redis_pool


async def enqueue_job(job_name: str, *args: Any, **kwargs: Any) -> str | None:
    """Enqueue a job for the worker. Returns the job id, or None if unavailable."""
    if _redis_pool is None:
        logger.warning("Background worker unavailable, skipping job: %s", job_name)
        return None
    try:
        job = await _redis_pool.enqueue_job(job_name, *args, **kwargs)
        return job.job_id if job else None
    except Exception:
        logger.exception("Failed to enqueue job: %s", job_name)
        return None


async def create_redis_pool() -> ArqRedis:
    return await create_pool(redis_settings())


# --- Job functions (executed by the worker process) --------------------------


async def send_email_job(
    _ctx: dict[str, Any],
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    """Send an email outside of the request/response cycle."""
    await asyncio.to_thread(
        send_email, email_to=email_to, subject=subject, html_content=html_content
    )


async def send_email_background(
    *, email_to: str, subject: str = "", html_content: str = ""
) -> None:
    """Enqueue an email, falling back to sending it inline if no worker is up."""
    job_id = await enqueue_job(
        "send_email_job",
        email_to=email_to,
        subject=subject,
        html_content=html_content,
    )
    if job_id is None and settings.emails_enabled:
        send_email(email_to=email_to, subject=subject, html_content=html_content)


async def process_payment_event_job(
    _ctx: dict[str, Any],
    *,
    provider: str,
    event_type: str,
    provider_event_id: str,
    amount_cents: int | None,
    currency: str | None,
    raw: str,
) -> None:
    """Persist a provider webhook event idempotently and reconcile subscription state."""
    from app.core.payments import get_payment_provider

    payment_provider = get_payment_provider()
    if payment_provider is None:
        logger.warning("No payment provider configured, ignoring webhook event")
        return

    payload = json.loads(raw)
    async with async_session_factory() as session:
        existing = (
            await session.exec(
                select(PaymentEvent).where(
                    PaymentEvent.provider_event_id == provider_event_id
                )
            )
        ).first()
        if existing:
            logger.info("Duplicate webhook event ignored: %s", provider_event_id)
            return

        event = PaymentEvent(
            user_id=None,
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            amount_cents=amount_cents,
            currency=currency,
            status="received",
            raw=raw,
        )
        session.add(event)
        try:
            outcome = await payment_provider.reconcile_event(
                session, event_type, payload
            )
            if outcome is not None:
                event.status = outcome
            await session.commit()
            logger.info("Processed webhook event %s: %s", provider_event_id, event_type)
        except Exception:
            logger.exception("Failed to reconcile webhook event %s", provider_event_id)
            await session.rollback()


# --- Outbound webhook delivery ----------------------------------------------

MAX_WEBHOOK_ATTEMPTS = 5
WEBHOOK_BACKOFF_SECONDS = [60, 300, 900, 3600]


async def deliver_webhook_job(
    _ctx: dict[str, Any], *, delivery_id: str, attempt: int = 1
) -> None:
    """Deliver a signed webhook payload, retrying with backoff on failure."""
    import hashlib
    import hmac

    import httpx

    from app.models import Webhook, WebhookDelivery

    async with async_session_factory() as session:
        delivery = (
            await session.exec(
                select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
            )
        ).first()
        if delivery is None:
            return
        webhook = (
            await session.exec(select(Webhook).where(Webhook.id == delivery.webhook_id))
        ).first()
        if webhook is None or not webhook.is_active:
            delivery.status = "failed"
            delivery.completed_at = get_utc_now()
            await session.commit()
            return

        payload_bytes = delivery.payload.encode("utf-8")
        signature = hmac.new(
            webhook.secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": delivery.event,
        }
        delivery.attempts = attempt
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    webhook.url, content=payload_bytes, headers=headers
                )
            delivery.response_status = response.status_code
            delivery.response_body = response.text[:2000]
            if 200 <= response.status_code < 300:
                delivery.status = "success"
                delivery.completed_at = get_utc_now()
            else:
                delivery.status = "failed"
                delivery.completed_at = get_utc_now()
            await session.commit()
            logger.info(
                "Webhook delivery %s -> %s (%s)",
                delivery.id,
                webhook.url,
                delivery.status,
            )
        except Exception as exc:
            logger.warning("Webhook delivery %s failed: %s", delivery.id, exc)
            if attempt < MAX_WEBHOOK_ATTEMPTS:
                backoff = WEBHOOK_BACKOFF_SECONDS[
                    min(attempt - 1, len(WEBHOOK_BACKOFF_SECONDS) - 1)
                ]
                delivery.status = "pending"
                delivery.next_retry_at = get_utc_now() + timedelta(seconds=backoff)
                await session.commit()
                await enqueue_job(
                    "deliver_webhook_job",
                    delivery_id=delivery_id,
                    attempt=attempt + 1,
                    _defer_by=backoff,
                )
            else:
                delivery.status = "failed"
                delivery.completed_at = get_utc_now()
                await session.commit()


# --- Scheduled jobs (ARQ cron) ----------------------------------------------


async def cleanup_expired_invites_job(_ctx: dict[str, Any]) -> None:
    """Mark expired organization invites as expired."""
    from datetime import UTC, datetime

    from app.models import INVITE_EXPIRED, INVITE_PENDING, OrganizationInvite

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
    """Purge old, revoked or expired auth sessions."""
    from datetime import UTC, datetime, timedelta

    from app.models import Session

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
    from app.models import ORG_ROLE_OWNER, OrganizationMember, Subscription, User

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


def get_utc_now():
    from datetime import UTC, datetime

    return datetime.now(UTC)
