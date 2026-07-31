"""Role, plan-tier and feature-access helpers.

Global user hierarchy:
    user  <  staff  <  admin == superuser

Per-tenant roles (see ``core/orgs.py``):
    viewer  <  member  <  admin  <  owner

Plans (billing tiers):
    free  <  pro  <  business  <  enterprise

When ``PAYMENT_PROVIDER`` is ``none`` (the default) plan gates are disabled and
every authenticated user gets full access. Once a payment provider is
configured, ``require_plan(...)`` and quotas are enforced against the active
organization's subscription.
"""

import json
import uuid
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.cache import cache_delete, cache_get, cache_set
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

_ACTIVE_PLAN_TTL = 60


def _active_plan_cache_key(organization_id: Any) -> str:
    return f"active_plan:{organization_id}"


async def invalidate_active_plan(organization_id: Any) -> None:
    await cache_delete(_active_plan_cache_key(organization_id))


def is_admin(user: User) -> bool:
    return user.is_superuser or user.role == ROLE_ADMIN


def is_staff(user: User) -> bool:
    return user.is_superuser or user.role in (ROLE_STAFF, ROLE_ADMIN)


def billing_enabled() -> bool:
    return settings.PAYMENT_PROVIDER != "none"


def plan_quota(plan: Plan | None, key: str, default: int = 0) -> int:
    """Read an integer quota from a plan's JSON ``quotas`` (0 = unlimited)."""
    if plan is None or not plan.quotas:
        return default
    try:
        data: dict[str, Any] = json.loads(plan.quotas)
        value = data.get(key, default)
        return int(value) if isinstance(value, (int, float)) else default
    except Exception:
        return default


async def get_active_plan(session: AsyncSession, organization_id: Any) -> Plan | None:
    """Return the active organization's current subscription plan, if any.

    Cached per organization (60s) and invalidated on subscription changes.
    """
    cached_id = await cache_get(_active_plan_cache_key(organization_id))
    if cached_id:
        plan = await session.get(Plan, uuid.UUID(str(cached_id)))
        if plan is not None:
            return plan
    subscription = (
        await session.exec(
            select(Subscription)
            .where(
                Subscription.organization_id == organization_id,
                col(Subscription.status).in_(["active", "trialing", "past_due"]),
            )
            .order_by(col(Subscription.created_at).desc())
        )
    ).first()
    if subscription is None or subscription.plan_id is None:
        return None
    plan = await session.get(Plan, subscription.plan_id)
    if plan is not None:
        await cache_set(
            _active_plan_cache_key(organization_id),
            str(plan.id),
            ttl_seconds=_ACTIVE_PLAN_TTL,
        )
    return plan


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
