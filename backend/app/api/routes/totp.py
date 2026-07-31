from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.core import security
from app.core.audit import audit_event
from app.models import (
    Message,
    TotpDisableRequest,
    TotpEnableRequest,
    TotpSetupRequest,
    TotpSetupResponse,
)

router = APIRouter(prefix="/auth/totp", tags=["auth"])


@router.post("/setup", response_model=TotpSetupResponse)
async def totp_setup(
    session: SessionDep, current_user: CurrentUser, body: TotpSetupRequest
) -> Any:
    """Begin 2FA setup: returns the secret + otpauth URL to scan."""
    verified, _ = security.verify_password(
        body.password, current_user.hashed_password or ""
    )
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="TOTP is already enabled")
    secret = security.generate_totp_secret()
    current_user.totp_secret = secret
    session.add(current_user)
    await session.commit()
    uri = security.totp_uri(secret, email=str(current_user.email))
    return TotpSetupResponse(secret=secret, otpauth_url=uri)


@router.post("/enable", response_model=Message)
async def totp_enable(
    session: SessionDep, current_user: CurrentUser, body: TotpEnableRequest
) -> Message:
    """Confirm a code from the authenticator app to enable 2FA."""
    if current_user.totp_secret is None:
        raise HTTPException(status_code=400, detail="Run setup first")
    if current_user.totp_enabled:
        return Message(message="TOTP already enabled")
    if not security.verify_totp(current_user.totp_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid code")
    current_user.totp_enabled = True
    session.add(current_user)
    await session.commit()
    await audit_event(
        action="auth.totp_enabled",
        user_id=current_user.id,
        detail={"email": str(current_user.email)},
    )
    return Message(message="TOTP enabled")


@router.post("/disable", response_model=Message)
async def totp_disable(
    session: SessionDep, current_user: CurrentUser, body: TotpDisableRequest
) -> Message:
    """Disable 2FA after verifying the current code."""
    if not current_user.totp_enabled or current_user.totp_secret is None:
        return Message(message="TOTP is not enabled")
    if not security.verify_totp(current_user.totp_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid code")
    current_user.totp_enabled = False
    current_user.totp_secret = None
    session.add(current_user)
    await session.commit()
    await audit_event(
        action="auth.totp_disabled",
        user_id=current_user.id,
        detail={"email": str(current_user.email)},
    )
    return Message(message="TOTP disabled")
