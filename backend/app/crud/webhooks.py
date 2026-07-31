"""Webhook repository."""

import json
from collections.abc import Sequence
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Webhook, WebhookDelivery


async def create_webhook(
    session: AsyncSession,
    *,
    organization_id: Any,
    url: str,
    secret: str,
    events: list[str],
) -> Webhook:
    webhook = Webhook(
        organization_id=organization_id,
        url=url,
        secret=secret,
        events=json.dumps(events or ["*"]),
    )
    session.add(webhook)
    await session.flush()
    return webhook


async def list_webhooks(
    session: AsyncSession, organization_id: Any
) -> Sequence[Webhook]:
    return (
        await session.exec(
            select(Webhook)
            .where(Webhook.organization_id == organization_id)
            .order_by(col(Webhook.created_at).desc())
        )
    ).all()


async def list_active_webhooks_for_event(
    session: AsyncSession, organization_id: Any
) -> Sequence[Webhook]:
    return (
        await session.exec(
            select(Webhook).where(
                Webhook.organization_id == organization_id,
                Webhook.is_active == True,  # noqa: E712
            )
        )
    ).all()


async def get_webhook(session: AsyncSession, webhook_id: Any) -> Webhook | None:
    return await session.get(Webhook, webhook_id)


async def update_webhook(
    session: AsyncSession,
    webhook: Webhook,
    *,
    url: str | None = None,
    is_active: bool | None = None,
    events: list[str] | None = None,
) -> Webhook:
    if url is not None:
        webhook.url = url
    if is_active is not None:
        webhook.is_active = is_active
    if events is not None:
        webhook.events = json.dumps(events)
    session.add(webhook)
    return webhook


async def create_delivery(
    session: AsyncSession,
    *,
    webhook_id: Any,
    event: str,
    payload: str,
) -> WebhookDelivery:
    delivery = WebhookDelivery(webhook_id=webhook_id, event=event, payload=payload)
    session.add(delivery)
    await session.flush()
    return delivery


async def list_deliveries(
    session: AsyncSession, webhook_id: Any, limit: int = 50
) -> Sequence[WebhookDelivery]:
    return (
        await session.exec(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(col(WebhookDelivery.created_at).desc())
            .limit(limit)
        )
    ).all()
