"""Notification repository."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Notification


async def create_notification(
    session: AsyncSession,
    *,
    user_id: Any,
    type: str,
    title: str,
    body: str | None = None,
) -> Notification:
    notification = Notification(user_id=user_id, type=type, title=title, body=body)
    session.add(notification)
    return notification


async def list_notifications(
    session: AsyncSession, user_id: Any, limit: int = 50
) -> Sequence[Notification]:
    return (
        await session.exec(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(col(Notification.created_at).desc())
            .limit(limit)
        )
    ).all()


async def count_unread(session: AsyncSession, user_id: Any) -> int:
    count = (
        await session.exec(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, col(Notification.read_at).is_(None))
        )
    ).one()
    return int(count)


async def mark_read(session: AsyncSession, notification: Notification) -> None:
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        session.add(notification)


async def mark_all_read(session: AsyncSession, user_id: Any) -> int:
    notifications = (
        await session.exec(
            select(Notification).where(
                Notification.user_id == user_id, col(Notification.read_at).is_(None)
            )
        )
    ).all()
    now = datetime.now(UTC)
    for notification in notifications:
        notification.read_at = now
        session.add(notification)
    return len(notifications)
