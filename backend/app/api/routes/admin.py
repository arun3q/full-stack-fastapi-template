from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import ReadSessionDep, SessionDep, get_current_active_superuser
from app.crud.audit import list_audit_logs
from app.crud.users import get_user_by_id
from app.models import (
    AuditLogPublic,
    AuditLogsPublic,
    Item,
    Message,
    Organization,
    OrganizationMember,
    Plan,
    PlanCreate,
    PlanPublic,
    PlansPublic,
    PlanUpdate,
    Subscription,
    User,
    UserPublic,
)

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = [Depends(get_current_active_superuser)]


@router.get("/overview", dependencies=admin_only)
async def admin_overview(session: ReadSessionDep) -> dict[str, int]:
    """Platform-wide counters + MRR for the admin console."""
    counts: dict[str, int] = {}
    for label, model in [
        ("users", User),
        ("organizations", Organization),
        ("items", Item),
        ("subscriptions", Subscription),
    ]:
        counts[label] = (
            await session.exec(select(func.count()).select_from(model))
        ).one()
    active_subs = (
        await session.exec(
            select(func.count())
            .select_from(Subscription)
            .where(col(Subscription.status) == "active")
        )
    ).one()
    counts["active_subscriptions"] = active_subs

    # Monthly recurring revenue (annualized to monthly; includes trialing)
    mrr_cents = 0
    active_subscriptions = (
        await session.exec(
            select(Subscription).where(
                col(Subscription.status).in_(["active", "trialing"])
            )
        )
    ).all()
    for subscription in active_subscriptions:
        plan = await session.get(Plan, subscription.plan_id)
        if plan is None:
            continue
        quantity = max(subscription.quantity, 1)
        if plan.billing_interval == "year":
            mrr_cents += (plan.amount_cents * quantity) // 12
        else:
            mrr_cents += plan.amount_cents * quantity
    counts["mrr_cents"] = mrr_cents
    counts["arr_cents"] = mrr_cents * 12
    return counts


@router.get("/organizations", dependencies=admin_only)
async def admin_organizations(
    session: ReadSessionDep,
    skip: int = 0,
    limit: int = 100,
    cursor: str | None = None,
) -> dict[str, Any]:
    """List organizations with their member counts."""
    from app.core.pagination import decode_cursor, encode_cursor

    statement = (
        select(Organization).order_by(col(Organization.created_at).desc()).limit(limit)
    )
    if cursor:
        keyset = decode_cursor(cursor)
        if keyset is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="Invalid cursor")
        cursor_created_at, cursor_id = keyset
        statement = statement.where(
            (col(Organization.created_at) < cursor_created_at)
            | (
                (col(Organization.created_at) == cursor_created_at)
                & (Organization.id < cursor_id)
            )
        )
    else:
        statement = statement.offset(skip)
    orgs = (await session.exec(statement)).all()

    # Single pass member counts (GROUP BY) to avoid N+1
    org_ids = [org.id for org in orgs]
    counts: dict[str, int] = {}
    if org_ids:
        rows = (
            await session.exec(
                select(
                    OrganizationMember.organization_id,
                    func.count(col(OrganizationMember.id)),
                )
                .where(col(OrganizationMember.organization_id).in_(org_ids))
                .group_by(col(OrganizationMember.organization_id))
            )
        ).all()
        for org_id, count in rows:
            counts[str(org_id)] = int(count)

    data: list[dict[str, Any]] = []
    for org in orgs:
        data.append(
            {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "member_count": counts.get(str(org.id), 0),
                "created_at": org.created_at,
            }
        )
    next_cursor = (
        encode_cursor(orgs[-1].created_at, orgs[-1].id)
        if orgs and len(orgs) == limit
        else None
    )
    return {"data": data, "count": len(data), "next_cursor": next_cursor}


@router.get("/users", dependencies=admin_only)
async def admin_users(
    session: ReadSessionDep, skip: int = 0, limit: int = 100
) -> dict[str, Any]:
    users_list, _ = await crud.list_users(session=session, skip=skip, limit=limit)
    return {
        "data": [UserPublic.model_validate(u) for u in users_list],
        "count": len(users_list),
    }


@router.patch("/users/{user_id}/status", dependencies=admin_only)
async def admin_set_user_status(
    session: SessionDep, user_id: Any, is_active: bool
) -> User:
    """Enable or disable a user account."""
    from uuid import UUID

    try:
        user_uuid = UUID(str(user_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
    user = await get_user_by_id(session=session, user_id=user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = is_active
    if not is_active:
        # Revoke all refresh sessions so the account can't keep refreshing
        from app.crud.sessions import revoke_all_sessions

        await revoke_all_sessions(session, user.id)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/audit-log", dependencies=admin_only, response_model=AuditLogsPublic)
async def admin_audit_log(
    session: ReadSessionDep,
    skip: int = 0,
    limit: int = 100,
    cursor: str | None = None,
) -> Any:
    """Recent platform audit-log entries."""
    try:
        entries, next_cursor = await list_audit_logs(
            session=session, skip=skip, limit=limit, cursor=cursor
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor")
    return {
        "data": [AuditLogPublic.model_validate(e) for e in entries],
        "count": len(entries),
        "next_cursor": next_cursor,
    }


# ---------- Plan management (platform admin) ----------


@router.get("/plans", dependencies=admin_only, response_model=PlansPublic)
async def admin_plans(session: ReadSessionDep) -> Any:
    """List all plans (active and inactive)."""
    plans = (await session.exec(select(Plan))).all()
    return PlansPublic(
        data=[PlanPublic.model_validate(plan) for plan in plans],
        count=len(plans),
    )


@router.post(
    "/plans", dependencies=admin_only, response_model=PlanPublic, status_code=201
)
async def admin_create_plan(session: SessionDep, body: PlanCreate) -> Any:
    """Create a plan."""
    from app.core.cache import cache_delete

    existing = (await session.exec(select(Plan).where(Plan.slug == body.slug))).first()
    if existing:
        raise HTTPException(status_code=409, detail="A plan with this slug exists")
    plan = Plan(**body.model_dump())
    session.add(plan)
    await session.commit()
    await cache_delete("plans")
    await session.refresh(plan)
    return plan


@router.patch("/plans/{plan_id}", dependencies=admin_only, response_model=PlanPublic)
async def admin_update_plan(
    session: SessionDep, plan_id: UUID, body: PlanUpdate
) -> Any:
    """Update a plan."""
    from app.core.cache import cache_delete

    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    data = body.model_dump(exclude_unset=True)
    plan.sqlmodel_update(data)
    session.add(plan)
    await session.commit()
    await cache_delete("plans")
    await session.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}", dependencies=admin_only, response_model=Message)
async def admin_delete_plan(session: SessionDep, plan_id: UUID) -> Message:
    """Deactivate a plan (or hard-delete when no subscriptions reference it)."""
    from app.core.cache import cache_delete

    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    referencing = (
        await session.exec(select(Subscription).where(Subscription.plan_id == plan.id))
    ).all()
    if referencing:
        plan.is_active = False
        session.add(plan)
        detail = "Plan deactivated (subscriptions still reference it)"
    else:
        await session.delete(plan)
        detail = "Plan deleted"
    await session.commit()
    await cache_delete("plans")
    return Message(message=detail)
