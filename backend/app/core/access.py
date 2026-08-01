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

import asyncio
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
_MISS = "__none__"

# In-process single-flight locks to dampen cache stampedes within a worker.
_inflight: dict[str, Any] = {}


def _active_plan_cache_key(organization_id: Any) -> str:
    return f"active_plan:{organization_id}"


async def invalidate_active_plan(organization_id: Any) -> None:
    _inflight.pop(_active_plan_cache_key(organization_id), None)
    await cache_delete(_active_plan_cache_key(organization_id))


def _plan_to_dict(plan: Plan) -> dict[str, Any]:
    return {
        "id": str(plan.id),
        "slug": plan.slug,
        "name": plan.name,
        "amount_cents": plan.amount_cents,
        "currency": plan.currency,
        "billing_interval": plan.billing_interval,
        "is_active": plan.is_active,
        "trial_days": plan.trial_days,
        "features": plan.features,
        "quotas": plan.quotas,
    }


def _plan_from_dict(data: dict[str, Any]) -> Plan:
    return Plan(
        id=uuid.UUID(str(data["id"])),
        slug=str(data["slug"]),
        name=str(data["name"]),
        amount_cents=int(data["amount_cents"]),
        currency=str(data["currency"]),
        billing_interval=str(data["billing_interval"]),
        is_active=bool(data["is_active"]),
        trial_days=int(data.get("trial_days", 0)),
        features=data.get("features"),
        quotas=data.get("quotas"),
    )


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

    Cached per organization (60s) as the full plan payload (with a miss
    sentinel) and invalidated on subscription changes. An in-process lock
    dampens cache stampedes within a worker.
    """
    key = _active_plan_cache_key(organization_id)

    async def _compute() -> Plan | None:
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
        plan = None
        if subscription is not None and subscription.plan_id is not None:
            plan = await session.get(Plan, subscription.plan_id)
        if plan is not None:
            await cache_set(key, _plan_to_dict(plan), ttl_seconds=_ACTIVE_PLAN_TTL)
        else:
            await cache_set(key, _MISS, ttl_seconds=_ACTIVE_PLAN_TTL)
        return plan

    cached = await cache_get(key)
    if cached is not None:
        return None if cached == _MISS else _plan_from_dict(cached)

    lock = _inflight.setdefault(key, asyncio.Lock())
    async with lock:
        # Double-check after acquiring the lock (another worker may have computed)
        cached = await cache_get(key)
        if cached is not None:
            return None if cached == _MISS else _plan_from_dict(cached)
        return await _compute()


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
