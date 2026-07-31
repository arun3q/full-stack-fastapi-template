"""Outbound webhook delivery: signed, with retries + backoff."""

import hashlib
import hmac
import logging
from datetime import timedelta
from typing import Any

import httpx
from sqlmodel import select

from app.core.db import async_session_factory
from app.core.jobs.base import enqueue_job, get_utc_now
from app.models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)

MAX_WEBHOOK_ATTEMPTS = 5
WEBHOOK_BACKOFF_SECONDS = [60, 300, 900, 3600]


async def deliver_webhook_job(
    _ctx: dict[str, Any], *, delivery_id: str, attempt: int = 1
) -> None:
    """Deliver a signed webhook payload, retrying with backoff on failure."""
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
        succeeded = False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    webhook.url, content=payload_bytes, headers=headers
                )
            delivery.response_status = response.status_code
            delivery.response_body = response.text[:2000]
            succeeded = 200 <= response.status_code < 300
        except Exception as exc:
            logger.warning("Webhook delivery %s failed: %s", delivery.id, exc)

        if succeeded:
            delivery.status = "success"
            delivery.completed_at = get_utc_now()
            await session.commit()
            logger.info("Webhook delivery %s -> %s (success)", delivery.id, webhook.url)
        elif attempt < MAX_WEBHOOK_ATTEMPTS:
            # Retry on both network errors and HTTP errors
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
