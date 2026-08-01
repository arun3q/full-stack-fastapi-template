from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import CurrentUser, SessionDep
from app.core import security
from app.core.audit import audit_event
from app.core.config import settings
from app.core.ratelimit import limiter
from app.crud.sessions import (
    create_session as create_session_record,
)
from app.crud.sessions import (
    get_session,
    get_session_by_refresh_hash,
    list_active_sessions,
    revoke_session,
)
from app.models import (
    Message,
    RefreshRequest,
    SessionPublic,
    SessionsPublic,
    Token,
    User,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/refresh", response_model=Token)
@limiter.limit("10/minute")
async def refresh_access_token(
    request: Request, session: SessionDep, body: RefreshRequest
) -> Token:
    """Rotate a refresh token: revoke it and issue a fresh access + refresh pair."""
    db_session = await get_session_by_refresh_hash(session, body.refresh_token)
    if db_session is None or db_session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if db_session.expires_at is not None and db_session.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = await session.get(User, db_session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")

    # Rotate
    await revoke_session(session, db_session)

    new_refresh, new_session = await create_session_record(
        session,
        user_id=db_session.user_id,
        ip_address=db_session.ip_address,
        user_agent=db_session.user_agent,
    )
    await session.commit()

    await audit_event(
        action="auth.refresh",
        user_id=db_session.user_id,
        ip_address=request.client.host if request.client else None,
    )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            db_session.user_id, expires_delta=access_token_expires
        ),
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=Message)
@limiter.limit("10/minute")
async def logout(
    request: Request, session: SessionDep, body: RefreshRequest
) -> Message:
    """Revoke the session associated with a refresh token."""
    db_session = await get_session_by_refresh_hash(session, body.refresh_token)
    if db_session is not None and db_session.revoked_at is None:
        await revoke_session(session, db_session)
        await session.commit()
        await audit_event(
            action="auth.logout",
            user_id=db_session.user_id,
            ip_address=request.client.host if request.client else None,
        )
    return Message(message="Logged out")


@router.get("/sessions", response_model=SessionsPublic)
async def read_sessions(session: SessionDep, current_user: CurrentUser) -> Any:
    """List the current user's active sessions."""
    sessions = await list_active_sessions(session, current_user.id)
    return {
        "data": [SessionPublic.model_validate(s) for s in sessions],
        "count": len(sessions),
    }


@router.delete("/sessions/{session_id}", response_model=Message)
async def revoke_session_route(
    session: SessionDep,
    current_user: CurrentUser,
    session_id: Any,
) -> Message:
    """Revoke one of the current user's sessions."""
    from uuid import UUID

    try:
        session_uuid = UUID(str(session_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    db_session = await get_session(session, session_uuid)
    if db_session is None or db_session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if db_session.revoked_at is None:
        await revoke_session(session, db_session)
        await session.commit()
    return Message(message="Session revoked")
