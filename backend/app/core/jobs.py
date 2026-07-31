"""Background job queue based on ARQ (backed by Redis).

Jobs are enqueued from request handlers and executed by a separate worker
process (see ``app/worker.py``). If Redis is unavailable the application keeps
working: enqueues fail gracefully and e.g. emails are sent inline as a fallback.
"""

import asyncio
import json
import logging
from typing import Any
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from sqlmodel import select

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
    if job_id is None:
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
