from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.crud.audit import list_audit_logs
from app.crud.users import get_user_by_id, list_users
from app.models import (
    AuditLogPublic,
    AuditLogsPublic,
    Item,
    Organization,
    OrganizationMember,
    Subscription,
    User,
    UserPublic,
)

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = [Depends(get_current_active_superuser)]


@router.get("/overview", dependencies=admin_only)
async def admin_overview(session: SessionDep) -> dict[str, int]:
    """Platform-wide counters for the admin console."""
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
    return counts


@router.get("/organizations", dependencies=admin_only)
async def admin_organizations(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> dict[str, Any]:
    """List organizations with their member counts."""
    orgs = (
        await session.exec(
            select(Organization)
            .order_by(col(Organization.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
    ).all()
    data: list[dict[str, Any]] = []
    for org in orgs:
        member_count = (
            await session.exec(
                select(func.count())
                .select_from(OrganizationMember)
                .where(OrganizationMember.organization_id == org.id)
            )
        ).one()
        data.append(
            {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "member_count": member_count,
                "created_at": org.created_at,
            }
        )
    return {"data": data, "count": len(data)}


@router.get("/users", dependencies=admin_only, response_model=list[UserPublic])
async def admin_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    users = await list_users(session=session, skip=skip, limit=limit)
    return [UserPublic.model_validate(u) for u in users]


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
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/audit-log", dependencies=admin_only, response_model=AuditLogsPublic)
async def admin_audit_log(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """Recent platform audit-log entries."""
    entries = await list_audit_logs(session=session, skip=skip, limit=limit)
    return {
        "data": [AuditLogPublic.model_validate(e) for e in entries],
        "count": len(entries),
    }
