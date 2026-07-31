"""Payment webhook processing: idempotent persistence + state reconciliation."""

import json
import logging
from typing import Any

from sqlmodel import select

from app.core.db import async_session_factory
from app.models import PaymentEvent, Subscription

logger = logging.getLogger(__name__)

# Outbound lifecycle events dispatched to customer webhooks
_LIFECYCLE_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
    "subscription.activated",
    "subscription.charged",
    "subscription.completed",
    "subscription.cancelled",
}


def _extract_subscription_id(payload: dict[str, Any]) -> str | None:
    obj = payload.get("data", {}).get("object", {})
    if isinstance(obj, dict):
        sub_id = (
            obj.get("id")
            if obj.get("object") == "subscription"
            else obj.get("subscription")
        )
        if sub_id:
            return str(sub_id)
    entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    if isinstance(entity, dict) and entity.get("id"):
        return str(entity["id"])
    return None


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
    from app.core.access import invalidate_active_plan
    from app.core.payments import get_payment_provider
    from app.core.webhooks import dispatch_webhooks

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

            # Attribute revenue/events to the tenant via the reconciled subscription
            sub_id = _extract_subscription_id(payload)
            if sub_id:
                subscription = (
                    await session.exec(
                        select(Subscription).where(
                            Subscription.provider_subscription_id == sub_id
                        )
                    )
                ).first()
                if (
                    subscription is not None
                    and subscription.organization_id is not None
                ):
                    event.organization_id = subscription.organization_id
                    await invalidate_active_plan(subscription.organization_id)
                    if event_type in _LIFECYCLE_EVENTS:
                        await dispatch_webhooks(
                            session,
                            organization_id=subscription.organization_id,
                            event=f"billing.{event_type}",
                            payload={
                                "event": event_type,
                                "subscription": str(subscription.id),
                                "organization": str(subscription.organization_id),
                            },
                        )

            await session.commit()
            logger.info("Processed webhook event %s: %s", provider_event_id, event_type)
        except Exception:
            logger.exception("Failed to reconcile webhook event %s", provider_event_id)
            # Persist the event as failed (durable record / DLQ substitute)
            event.status = "failed"
            try:
                await session.commit()
            except Exception:
                await session.rollback()
