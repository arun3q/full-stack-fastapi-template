"""Outbound webhooks: dispatch signed events to customer-configured endpoints."""

import ipaddress
import json
import logging
from typing import Any
from urllib.parse import urlparse

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.jobs import enqueue_job
from app.crud.webhooks import create_delivery, list_active_webhooks_for_event

logger = logging.getLogger(__name__)


def validate_webhook_url(url: str) -> None:
    """Reject webhook URLs that are SSRF hazards (private/metadata targets)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise ValueError("Webhook URL must use http(s) with a host")
    host = parsed.hostname
    if host in ("localhost", "127.0.0.1", "::1") and settings.ENVIRONMENT != "local":
        raise ValueError("Localhost webhook URLs are not allowed outside local")
    if host == "169.254.169.254":
        raise ValueError("Webhook URL must not target cloud metadata services")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # hostname -> resolved at delivery time
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise ValueError("Webhook URL must not point to private networks")


async def dispatch_webhooks(
    session: AsyncSession,
    *,
    organization_id: Any,
    event: str,
    payload: dict[str, Any],
) -> None:
    """Create a delivery for every active webhook subscribed to ``event``."""
    webhooks = await list_active_webhooks_for_event(session, organization_id)
    for webhook in webhooks:
        events = _parse_events(webhook.events)
        if event not in events and "*" not in events:
            continue
        delivery = await create_delivery(
            session,
            webhook_id=webhook.id,
            event=event,
            payload=json.dumps(payload, default=str),
        )
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
