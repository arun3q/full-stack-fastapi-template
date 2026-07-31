"""Role, plan-tier and feature-access helpers.

User hierarchy:
    user  <  staff  <  admin == superuser

Plans (billing tiers):
    free  <  pro  <  business  <  enterprise

When ``PAYMENT_PROVIDER`` is ``none`` (the default) plan gates are disabled and
every authenticated user gets full access. Once a payment provider is
configured, ``require_plan(...)`` and the item quota are enforced.
"""

from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import (
    ROLE_ADMIN,
    ROLE_STAFF,
    Plan,
    Subscription,
    User,
)

AI_PLANS = ("pro", "business", "enterprise")
UNLIMITED_PLANS = ("business", "enterprise")
FREE_PLAN_SLUG = "free"
MAX_FREE_ITEMS = 5


def is_admin(user: User) -> bool:
    return user.is_superuser or user.role == ROLE_ADMIN


def is_staff(user: User) -> bool:
    return user.is_superuser or user.role in (ROLE_STAFF, ROLE_ADMIN)


def billing_enabled() -> bool:
    return settings.PAYMENT_PROVIDER != "none"


async def get_active_plan(session: AsyncSession, user_id: Any) -> Plan | None:
    """Return the user's current active/trialing subscription plan, if any."""
    subscription = (
        await session.exec(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                col(Subscription.status).in_(["active", "trialing", "past_due"]),
            )
            .order_by(col(Subscription.created_at).desc())
        )
    ).first()
    if subscription is None or subscription.plan_id is None:
        return None
    return await session.get(Plan, subscription.plan_id)


def resolve_features(*, user: User, plan: Plan | None) -> list[str]:
    """Resolve the list of feature flags available to a user."""
    features: list[str] = ["items:create", "items:read", "billing"]

    if is_admin(user):
        features.extend(["admin", "staff", "ai:chat", "items:unlimited"])
    elif user.role == ROLE_STAFF:
        features.extend(["staff", "ai:chat", "items:unlimited"])

    if not billing_enabled():
        # No billing configured -> nothing is gated
        features.extend(["ai:chat", "items:unlimited"])
    else:
        slug = plan.slug if plan else None
        if slug in AI_PLANS:
            features.append("ai:chat")
        if slug in UNLIMITED_PLANS:
            features.append("items:unlimited")

    return sorted(set(features))
