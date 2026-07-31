"""In-app notifications."""

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Notification


async def notify(
    session: AsyncSession,
    *,
    user_id: Any,
    type: str = "info",
    title: str,
    body: str | None = None,
) -> None:
    session.add(
        Notification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
        )
    )
