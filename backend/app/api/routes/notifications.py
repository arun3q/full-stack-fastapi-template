from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.crud.notifications import (
    count_unread,
    list_notifications,
    mark_all_read,
    mark_read,
)
from app.models import Notification, NotificationPublic, NotificationsPublic

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationsPublic)
async def read_notifications(session: SessionDep, current_user: CurrentUser) -> Any:
    notifications = await list_notifications(session, current_user.id)
    return {
        "data": [NotificationPublic.model_validate(n) for n in notifications],
        "count": len(notifications),
    }


@router.get("/unread-count", response_model=dict[str, int])
async def unread_count(session: SessionDep, current_user: CurrentUser) -> Any:
    return {"count": await count_unread(session, current_user.id)}


@router.post("/{notification_id}/read", response_model=NotificationPublic)
async def mark_read_route(
    session: SessionDep, current_user: CurrentUser, notification_id: Any
) -> Any:
    from uuid import UUID

    try:
        notification_uuid = UUID(str(notification_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification = await session.get(Notification, notification_uuid)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    await mark_read(session, notification)
    await session.commit()
    return notification


@router.post("/read-all", response_model=dict[str, int])
async def mark_all_read_route(session: SessionDep, current_user: CurrentUser) -> Any:
    count = await mark_all_read(session, current_user.id)
    await session.commit()
    return {"count": count}
