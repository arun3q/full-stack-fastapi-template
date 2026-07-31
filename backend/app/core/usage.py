"""Usage metering and quota enforcement.

Plans carry JSON quotas (e.g. ``{"ai_calls": 50, "storage_bytes": 104857600}``);
usage is recorded to ``UsageEvent`` and checked with ``check_quota`` before an
operation consumes a metered resource. Quota ``0`` means unlimited.
"""

from datetime import UTC, datetime
from typing import Any

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.access import get_active_plan, plan_quota
from app.models import Plan, UsageEvent


async def record_usage(
    session: AsyncSession,
    *,
    organization_id: Any,
    meter: str,
    amount: int = 1,
    user_id: Any = None,
) -> None:
    session.add(
        UsageEvent(
            organization_id=organization_id,
            user_id=user_id,
            meter=meter,
            amount=amount,
        )
    )


async def get_usage(
    session: AsyncSession,
    *,
    organization_id: Any,
    meter: str,
    since: datetime | None = None,
) -> int:
    statement = (
        select(func.coalesce(func.sum(UsageEvent.amount), 0))
        .select_from(UsageEvent)
        .where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.meter == meter,
        )
    )
    if since is not None:
        statement = statement.where(col(UsageEvent.created_at) >= since)
    value = (await session.exec(statement)).one()
    return int(value or 0)


def quota_for(plan: Plan | None, meter: str) -> int:
    """Return the plan's quota for a meter (0 = unlimited)."""
    return plan_quota(plan, meter, default=0)


async def check_quota(
    session: AsyncSession,
    *,
    organization_id: Any,
    meter: str,
    amount: int = 1,
    plan: Plan | None = None,
) -> bool:
    """True if the org may consume ``amount`` of ``meter`` under its plan."""
    if plan is None:
        plan = await get_active_plan(session, organization_id)
    quota = quota_for(plan, meter)
    if quota <= 0:
        return True
    usage = await usage_this_month(
        session, organization_id=organization_id, meter=meter
    )
    return usage + amount <= quota


async def usage_this_month(
    session: AsyncSession, *, organization_id: Any, meter: str
) -> int:
    now = datetime.now(UTC)
    since = datetime(now.year, now.month, 1, tzinfo=UTC)
    return await get_usage(
        session, organization_id=organization_id, meter=meter, since=since
    )
