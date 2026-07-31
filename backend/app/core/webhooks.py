"""Outbound webhooks: dispatch signed events to customer-configured endpoints."""

import json
import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.jobs import enqueue_job
from app.models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BACKOFF_SECONDS = [60, 300, 900, 3600]


async def dispatch_webhooks(
    session: AsyncSession,
    *,
    organization_id: Any,
    event: str,
    payload: dict[str, Any],
) -> None:
    """Create a delivery for every active webhook subscribed to ``event``."""
    webhooks = (
        await session.exec(
            select(Webhook).where(
                Webhook.organization_id == organization_id,
                Webhook.is_active == True,  # noqa: E712
            )
        )
    ).all()
    for webhook in webhooks:
        events = _parse_events(webhook.events)
        if event not in events and "*" not in events:
            continue
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event=event,
            payload=json.dumps(payload, default=str),
        )
        session.add(delivery)
        await session.flush()
        await enqueue_job(
            "deliver_webhook_job", delivery_id=str(delivery.id), attempt=1
        )
        logger.info("Queued webhook delivery %s for event %s", delivery.id, event)


def _parse_events(raw: str) -> list[str]:
    try:
        parsed: Any = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []
