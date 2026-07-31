import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import col, select

from app.api.deps import CurrentOrg, CurrentUser, ReadSessionDep, SessionDep
from app.core.cache import cached
from app.core.config import settings
from app.core.jobs import enqueue_job
from app.core.payments import (
    BillingPortalProvider,
    PaymentError,
    get_payment_provider,
)
from app.models import (
    Message,
    Plan,
    PlanPublic,
    PlansPublic,
    Subscription,
    SubscriptionPublic,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/plans", response_model=PlansPublic)
@cached(lambda *args, **kwargs: "plans", ttl_seconds=60)
async def read_plans(session: ReadSessionDep) -> Any:
    """List all active plans available for subscription."""
    plans = (
        await session.exec(select(Plan).where(Plan.is_active == True))  # noqa: E712
    ).all()
    return PlansPublic(
        data=[PlanPublic.model_validate(plan) for plan in plans], count=len(plans)
    )


@router.post("/checkout", response_model=dict[str, str])
async def create_checkout(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    current_org: CurrentOrg,
    plan_id: str,
) -> Any:
    """
    Create a checkout session for a plan for the active organization.
    Returns ``{id, url}``; the frontend redirects the user to ``url``.
    """
    provider = get_payment_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="No payment provider configured")
    plan = (await session.exec(select(Plan).where(Plan.id == plan_id))).first()
    if not plan or not plan.is_active:
        raise HTTPException(status_code=404, detail="Plan not found")
    try:
        session_data = await provider.create_checkout_session(
            plan=plan,
            organization=current_org,
            user=current_user,
            success_url=f"{settings.FRONTEND_HOST}/billing?success=true",
            cancel_url=f"{settings.FRONTEND_HOST}/billing?canceled=true",
        )
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"id": session_data["id"], "url": session_data["url"]}


@router.post("/webhook")
async def payments_webhook(request: Request, _session: SessionDep) -> dict[str, bool]:
    """
    Provider webhook endpoint. The raw body is verified against the provider's
    signature, then handed off to the background worker for idempotent
    processing so the webhook responds immediately.
    """
    provider = get_payment_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="No payment provider configured")

    payload = await request.body()
    signature = request.headers.get("Stripe-Signature") or request.headers.get(
        "X-Razorpay-Signature"
    )
    if not signature or not await provider.verify_webhook_signature(
        payload=payload, signature=signature
    ):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from e

    event_type = data.get("type") or data.get("event")
    provider_event_id = (
        data.get("id") or data.get("event_id") or f"{provider.name}-{event_type}"
    )
    obj = data.get("data", {}).get("object", {}) or data.get("payload", {}).get(
        "subscription", {}
    ).get("entity", {})
    await enqueue_job(
        "process_payment_event_job",
        provider=provider.name,
        event_type=event_type or "unknown",
        provider_event_id=str(provider_event_id),
        amount_cents=obj.get("amount_total") or obj.get("amount"),
        currency=obj.get("currency"),
        raw=payload.decode("utf-8"),
    )
    return {"received": True}


@router.get("/subscription", response_model=SubscriptionPublic | None)
async def read_subscription(session: SessionDep, current_org: CurrentOrg) -> Any:
    """Return the active organization's most recent subscription, if any."""
    subscription = (
        await session.exec(
            select(Subscription)
            .where(
                Subscription.organization_id == current_org.id,
                col(Subscription.status).in_(["active", "trialing", "past_due"]),
            )
            .order_by(col(Subscription.created_at).desc())
        )
    ).first()
    if subscription is None:
        return None
    plan = await session.get(Plan, subscription.plan_id)
    data = SubscriptionPublic.model_validate(subscription)
    data.plan = PlanPublic.model_validate(plan) if plan else None
    return data


@router.post("/subscription/cancel", response_model=Message)
async def cancel_subscription(session: SessionDep, current_org: CurrentOrg) -> Any:
    """Cancel the active organization's subscription."""
    provider = get_payment_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="No payment provider configured")
    subscription = (
        await session.exec(
            select(Subscription).where(
                Subscription.organization_id == current_org.id,
                col(Subscription.status).in_(["active", "trialing", "past_due"]),
            )
        )
    ).first()
    if not subscription or not subscription.provider_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")
    try:
        await provider.cancel_subscription(
            provider_subscription_id=subscription.provider_subscription_id
        )
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    subscription.status = "canceled"
    subscription.cancel_at_period_end = True
    session.add(subscription)
    await session.commit()
    return Message(message="Subscription canceled")


@router.post("/portal", response_model=dict[str, str])
async def billing_portal(session: SessionDep, current_org: CurrentOrg) -> Any:
    """Create a billing portal session and return its URL (providers that support it)."""
    provider = get_payment_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="No payment provider configured")
    if not isinstance(provider, BillingPortalProvider):
        raise HTTPException(
            status_code=400, detail="Billing portal is not supported by this provider"
        )
    subscription = (
        await session.exec(
            select(Subscription).where(Subscription.organization_id == current_org.id)
        )
    ).first()
    if not subscription or not subscription.provider_customer_id:
        raise HTTPException(status_code=404, detail="No customer found")
    try:
        url = await provider.create_billing_portal_session(
            customer_id=subscription.provider_customer_id,
            return_url=f"{settings.FRONTEND_HOST}/billing",
        )
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"url": url}
