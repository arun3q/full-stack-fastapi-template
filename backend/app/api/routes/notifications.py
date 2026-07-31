from typing import Any

from fastapi import APIRouter
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Notification, NotificationPublic, NotificationsPublic

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationsPublic)
async def read_notifications(session: SessionDep, current_user: CurrentUser) -> Any:
    notifications = (
        await session.exec(
            select(Notification)
            .where(Notification.user_id == current_user.id)
            .order_by(col(Notification.created_at).desc())
            .limit(50)
        )
    ).all()
    return {
        "data": [NotificationPublic.model_validate(n) for n in notifications],
        "count": len(notifications),
    }


@router.get("/unread-count", response_model=dict[str, int])
async def unread_count(session: SessionDep, current_user: CurrentUser) -> Any:
    count = (
        await session.exec(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == current_user.id,
                col(Notification.read_at).is_(None),
            )
        )
    ).one()
    return {"count": int(count)}


@router.post("/{notification_id}/read", response_model=NotificationPublic)
async def mark_read(
    session: SessionDep, current_user: CurrentUser, notification_id: Any
) -> Any:
    from datetime import UTC, datetime

    from fastapi import HTTPException

    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        session.add(notification)
        await session.commit()
    return notification


@router.post("/read-all", response_model=dict[str, int])
async def mark_all_read(session: SessionDep, current_user: CurrentUser) -> Any:
    from datetime import UTC, datetime

    notifications = (
        await session.exec(
            select(Notification).where(
                Notification.user_id == current_user.id,
                col(Notification.read_at).is_(None),
            )
        )
    ).all()
    now = datetime.now(UTC)
    for notification in notifications:
        notification.read_at = now
        session.add(notification)
    await session.commit()
    return {"count": len(notifications)}
