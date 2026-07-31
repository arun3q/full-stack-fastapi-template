"""Payment provider abstraction supporting Stripe and Razorpay.

Providers implement the ``CheckoutProvider`` interface; ``BillingPortalProvider``
is an optional capability (Stripe). Swap providers through the
``PAYMENT_PROVIDER`` setting (``stripe`` | ``razorpay`` | ``none``).

Subscriptions belong to an **organization** (tenant). All external SDK calls are
run in a worker thread so they never block the event loop.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, cast

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import Organization, Plan, Subscription, User

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Raised when a payment provider operation fails."""


def _dt_from_unix(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC)


async def _find_active_plan(session: AsyncSession) -> Plan | None:
    return (await session.exec(select(Plan).where(Plan.is_active == True))).first()  # noqa: E712


async def _find_plan_by_price(
    session: AsyncSession, price_id: str | None
) -> Plan | None:
    if not price_id:
        return None
    return (
        await session.exec(select(Plan).where(Plan.provider_plan_id == price_id))
    ).first()


async def _find_subscription_by_provider_id(
    session: AsyncSession, provider_subscription_id: str | None
) -> Subscription | None:
    if not provider_subscription_id:
        return None
    return (
        await session.exec(
            select(Subscription).where(
                Subscription.provider_subscription_id == provider_subscription_id
            )
        )
    ).first()


async def _find_subscription_by_customer(
    session: AsyncSession, customer_id: str | None
) -> Subscription | None:
    if not customer_id:
        return None
    return (
        await session.exec(
            select(Subscription).where(Subscription.provider_customer_id == customer_id)
        )
    ).first()


async def _get_or_create_subscription(
    session: AsyncSession,
    *,
    organization_id: str | None,
    user_id: str | None = None,
    provider_subscription_id: str | None,
    provider_customer_id: str | None,
    status: str,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    plan_id: uuid.UUID | None = None,
) -> Subscription:
    existing = await _find_subscription_by_provider_id(
        session, provider_subscription_id
    )
    if existing:
        existing.status = status
        existing.provider_customer_id = provider_customer_id
        existing.current_period_start = period_start
        existing.current_period_end = period_end
        if plan_id:
            existing.plan_id = plan_id
        session.add(existing)
        return existing

    plan = None
    if plan_id:
        plan = (await session.exec(select(Plan).where(Plan.id == plan_id))).first()
    if plan is None:
        plan = await _find_active_plan(session)

    subscription = Subscription(
        organization_id=cast(Any, organization_id),
        user_id=cast(Any, user_id),
        plan_id=plan.id if plan else None,
        provider="stripe" if settings.PAYMENT_PROVIDER == "stripe" else "razorpay",
        provider_subscription_id=provider_subscription_id,
        provider_customer_id=provider_customer_id,
        status=status,
        current_period_start=period_start,
        current_period_end=period_end,
    )
    session.add(subscription)
    return subscription


class CheckoutProvider(ABC):
    """Interface implemented by every subscription provider (Stripe, Razorpay)."""

    name: str

    @abstractmethod
    async def create_checkout_session(
        self,
        *,
        plan: Plan,
        organization: Organization,
        user: User,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        """Create a hosted checkout session. Returns ``{"id", "url"}``."""

    @abstractmethod
    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        """Cancel a subscription with the provider."""

    @abstractmethod
    async def verify_webhook_signature(self, *, payload: bytes, signature: str) -> bool:
        """Verify the authenticity of a webhook payload."""

    @abstractmethod
    async def reconcile_event(
        self, session: AsyncSession, event_type: str, payload: dict[str, Any]
    ) -> str:
        """Update local state for a provider webhook event. Returns a status."""


class BillingPortalProvider(ABC):
    """Optional capability: a hosted customer billing portal."""

    @abstractmethod
    async def create_billing_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> str:
        """Create a customer billing portal session and return its URL."""


class StripeProvider(CheckoutProvider, BillingPortalProvider):
    name = "stripe"

    def __init__(self) -> None:
        import stripe

        self._stripe = stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

    async def create_checkout_session(
        self,
        *,
        plan: Plan,
        organization: Organization,
        user: User,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        price_id = plan.provider_plan_id or settings.STRIPE_PRICE_ID
        if not price_id:
            raise PaymentError(
                "Stripe price not configured for this plan (provider_plan_id)"
            )
        session = await asyncio.to_thread(
            self._stripe.checkout.Session.create,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(organization.id),
            customer_email=user.email,
            metadata={
                "plan_slug": plan.slug,
                "organization_id": str(organization.id),
                "user_id": str(user.id),
            },
            allow_promotion_codes=True,
            billing_address_collection="auto",
        )
        return {"id": session.id, "url": session.url}

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        await asyncio.to_thread(
            self._stripe.Subscription.cancel,
            provider_subscription_id,
        )

    async def create_billing_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> str:
        portal = await asyncio.to_thread(
            self._stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
        )
        return portal.url

    async def verify_webhook_signature(self, *, payload: bytes, signature: str) -> bool:
        if not settings.STRIPE_WEBHOOK_SECRET:
            return False
        try:
            self._stripe.Webhook.construct_event(
                payload, signature, settings.STRIPE_WEBHOOK_SECRET
            )  # type: ignore[no-untyped-call]
            return True
        except Exception:
            logger.exception("Stripe webhook signature verification failed")
            return False

    async def reconcile_event(
        self, session: AsyncSession, event_type: str, payload: dict[str, Any]
    ) -> str:
        obj = payload.get("data", {}).get("object", {})

        if event_type == "checkout.session.completed":
            organization_id = obj.get("client_reference_id")
            metadata = obj.get("metadata") or {}
            if organization_id:
                await _get_or_create_subscription(
                    session,
                    organization_id=str(organization_id),
                    user_id=metadata.get("user_id"),
                    provider_subscription_id=obj.get("subscription"),
                    provider_customer_id=obj.get("customer"),
                    status="active"
                    if obj.get("payment_status") == "paid"
                    else "incomplete",
                )
            return "processed"

        if event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            sub_id = obj.get("id")
            customer_id = obj.get("customer")
            items = obj.get("items", {}).get("data", [])
            price_id = items[0].get("price", {}).get("id") if items else None
            plan = await _find_plan_by_price(session, price_id)
            existing = await _find_subscription_by_provider_id(session, sub_id)
            org_id = str(existing.organization_id) if existing else None
            if org_id is None:
                by_customer = await _find_subscription_by_customer(session, customer_id)
                org_id = str(by_customer.organization_id) if by_customer else None
            status = obj.get("status") or "active"
            if event_type == "customer.subscription.deleted":
                status = "canceled"
            await _get_or_create_subscription(
                session,
                organization_id=org_id,
                user_id=str(existing.user_id) if existing else None,
                provider_subscription_id=sub_id,
                provider_customer_id=customer_id,
                status=status,
                period_start=_dt_from_unix(obj.get("current_period_start")),
                period_end=_dt_from_unix(obj.get("current_period_end")),
                plan_id=plan.id if plan else None,
            )
            return "processed"

        if event_type in {"invoice.payment_failed", "invoice.payment_action_required"}:
            subscription = await _find_subscription_by_provider_id(
                session, obj.get("subscription")
            )
            if subscription:
                subscription.status = "past_due"
                session.add(subscription)
            return "processed"

        if event_type == "invoice.paid":
            subscription = await _find_subscription_by_provider_id(
                session, obj.get("subscription")
            )
            if subscription:
                subscription.status = "active"
                subscription.current_period_end = _dt_from_unix(obj.get("period_end"))
                session.add(subscription)
            return "processed"

        logger.info("Unhandled Stripe event: %s", event_type)
        return "skipped"


class RazorpayProvider(CheckoutProvider):
    name = "razorpay"

    def _client(self) -> Any:
        import razorpay

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise PaymentError("Razorpay credentials not configured")
        return razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

    async def create_checkout_session(
        self,
        *,
        plan: Plan,
        organization: Organization,
        user: User,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        plan_id = plan.provider_plan_id or settings.RAZORPAY_PLAN_ID
        if not plan_id:
            raise PaymentError(
                "Razorpay plan not configured for this plan (provider_plan_id)"
            )
        client = self._client()

        def _create() -> Any:
            return client.subscription.create(
                {
                    "plan_id": plan_id,
                    "customer_notify": 1,
                    "quantity": 1,
                    "total_count": 12,
                    "notes": {
                        "organization_id": str(organization.id),
                        "plan_slug": plan.slug,
                        "user_id": str(user.id),
                    },
                }
            )

        subscription = await asyncio.to_thread(_create)
        return {
            "id": str(subscription["id"]),
            "url": str(subscription.get("short_url") or ""),
        }

    async def cancel_subscription(self, *, provider_subscription_id: str) -> None:
        client = self._client()
        await asyncio.to_thread(client.subscription.cancel, provider_subscription_id, 0)

    async def verify_webhook_signature(self, *, payload: bytes, signature: str) -> bool:
        """Razorpay signs webhooks with HMAC-SHA256 of the raw body."""
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            return False
        import hashlib
        import hmac

        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def reconcile_event(
        self, session: AsyncSession, event_type: str, payload: dict[str, Any]
    ) -> str:
        entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        sub_id = entity.get("id")
        if not sub_id:
            entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            sub_id = entity.get("subscription_id")

        status_map = {
            "subscription.activated": "active",
            "subscription.charged": "active",
            "subscription.completed": "completed",
            "subscription.halted": "halted",
            "subscription.paused": "paused",
            "subscription.pending": "pending",
            "subscription.cancelled": "canceled",
        }
        status = status_map.get(event_type)
        notes = entity.get("notes", {}) or {}
        organization_id = notes.get("organization_id")

        if sub_id:
            existing = await _find_subscription_by_provider_id(session, sub_id)
            if existing and status:
                existing.status = status
                session.add(existing)
            elif existing is None and organization_id:
                await _get_or_create_subscription(
                    session,
                    organization_id=str(organization_id),
                    user_id=notes.get("user_id"),
                    provider_subscription_id=sub_id,
                    provider_customer_id=entity.get("customer_id"),
                    status=status or "active",
                )
        return "processed" if status else "skipped"


def get_payment_provider() -> CheckoutProvider | None:
    if settings.PAYMENT_PROVIDER == "stripe":
        return StripeProvider()
    if settings.PAYMENT_PROVIDER == "razorpay":
        return RazorpayProvider()
    return None
