from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security
from app.core.audit import audit_event
from app.core.config import settings
from app.core.jobs import send_email_background
from app.core.ratelimit import (
    clear_login_failures,
    is_login_locked,
    limiter,
    record_login_failure,
)
from app.crud.sessions import revoke_all_sessions
from app.models import Message, NewPassword, Session, Token, UserPublic, UserUpdate
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


def _client_context(request: Request) -> tuple[str | None, str | None]:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return client_ip, user_agent


async def _create_session(
    session: SessionDep, user_id: Any, request: Request
) -> tuple[str, Session]:
    refresh_token = security.generate_refresh_token()
    client_ip, user_agent = _client_context(request)
    db_session = Session(
        user_id=user_id,
        refresh_token_hash=security.hash_refresh_token(refresh_token),
        ip_address=client_ip,
        user_agent=user_agent,
        expires_at=datetime.now(UTC)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(db_session)
    await session.flush()
    return refresh_token, db_session


@router.post("/login/access-token")
@limiter.limit("10/minute")
async def login_access_token(
    request: Request,
    response: Response,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    totp_code: Annotated[str | None, Form()] = None,
) -> Token:
    """
    OAuth2 compatible token login. Returns an access token plus a refresh
    token (session). Requires a TOTP code when the user has 2FA enabled.
    """
    client_ip, _ = _client_context(request)

    if await is_login_locked(form_data.username):
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Try again later.",
        )

    user = await crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        await record_login_failure(form_data.username)
        await audit_event(
            action="auth.login_failed",
            ip_address=client_ip,
            detail={"email": form_data.username},
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    if user.totp_enabled:
        if not totp_code or not security.verify_totp(user.totp_secret or "", totp_code):
            await audit_event(
                action="auth.totp_failed",
                user_id=user.id,
                ip_address=client_ip,
            )
            raise HTTPException(
                status_code=400, detail="TOTP code is required or invalid"
            )

    await clear_login_failures(form_data.username)
    refresh_token, _ = await _create_session(session, user.id, request)
    await session.commit()

    await audit_event(
        action="auth.login",
        user_id=user.id,
        ip_address=client_ip,
    )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.id, expires_delta=access_token_expires
    )
    if settings.AUTH_TOKEN_IN_COOKIE:
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=settings.ENVIRONMENT != "local",
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        import secrets as _secrets

        response.set_cookie(
            key="csrf_token",
            value=_secrets.token_urlsafe(32),
            httponly=False,
            secure=settings.ENVIRONMENT != "local",
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login/test-token", response_model=UserPublic)
async def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/password-recovery/{email}")
@limiter.limit("5/hour")
async def recover_password(
    request: Request,  # noqa: ARG001 - required by the rate limiter
    email: str,
    session: SessionDep,
) -> Message:
    """
    Password Recovery
    """
    user = await crud.get_user_by_email(session=session, email=email)

    # Always return the same response to prevent email enumeration attacks
    # Only send email if user actually exists
    if user:
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        await send_email_background(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password/")
async def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await crud.get_user_by_email(session=session, email=email)
    if not user:
        # Don't reveal that the user doesn't exist - use same error as invalid token
        raise HTTPException(status_code=400, detail="Invalid token")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    user_in_update = UserUpdate(password=body.new_password)
    await crud.update_user(
        session=session,
        db_user=user,
        user_in=user_in_update,
    )
    # Password reset invalidates all existing refresh sessions
    await revoke_all_sessions(session, user.id)
    await session.commit()
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
async def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = await crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
