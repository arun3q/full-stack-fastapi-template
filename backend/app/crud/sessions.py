"""Auth session repository (refresh tokens)."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security import generate_refresh_token, hash_refresh_token
from app.models import Session


async def create_session(
    session: AsyncSession,
    *,
    user_id: Any,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, Session]:
    refresh_token = generate_refresh_token()
    db_session = Session(
        user_id=user_id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=datetime.now(UTC)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(db_session)
    await session.flush()
    return refresh_token, db_session


async def get_session_by_refresh_hash(
    session: AsyncSession, refresh_token: str
) -> Session | None:
    return (
        await session.exec(
            select(Session).where(
                Session.refresh_token_hash == hash_refresh_token(refresh_token)
            )
        )
    ).first()


async def revoke_session(session: AsyncSession, db_session: Session) -> None:
    db_session.revoked_at = datetime.now(UTC)
    session.add(db_session)


async def list_active_sessions(
    session: AsyncSession, user_id: Any
) -> Sequence[Session]:
    return (
        await session.exec(
            select(Session)
            .where(Session.user_id == user_id, col(Session.revoked_at).is_(None))
            .order_by(col(Session.last_used_at).desc())
        )
    ).all()


async def get_session(session: AsyncSession, session_id: Any) -> Session | None:
    return await session.get(Session, session_id)
