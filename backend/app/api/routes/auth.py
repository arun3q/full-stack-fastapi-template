import uuid
from datetime import timedelta
from typing import Any

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import select

from app.api.deps import SessionDep
from app.core import security
from app.core.config import settings
from app.core.oauth import get_configured_providers, get_provider_userinfo, oauth
from app.models import OAuthAccount, User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/providers")
def auth_providers() -> dict[str, list[str]]:
    """List the OAuth providers that are currently configured."""
    return {"providers": get_configured_providers()}


@router.get("/{provider}")
async def auth_login(provider: str, request: Request) -> Any:
    """Redirect the user to the provider's authorization page."""
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(
            status_code=404,
            detail=f"OAuth provider '{provider}' is not configured",
        )
    redirect_uri = request.url_for("oauth_callback", provider=provider)
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str, request: Request, session: SessionDep
) -> RedirectResponse:
    """
    Exchange the authorization code, create/link the user and redirect back to
    the frontend with an access token (``/auth/callback?token=...``).
    """
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(
            status_code=404,
            detail=f"OAuth provider '{provider}' is not configured",
        )
    try:
        token = await client.authorize_access_token(request)
    except OAuthError as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {e.error}") from e

    user_info = await get_provider_userinfo(client, provider)
    provider_account_id = user_info.get("id") or str(uuid.uuid4())
    email = user_info.get("email")
    name = user_info.get("name")

    account = (
        await session.exec(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
        )
    ).first()

    if account:
        user = await session.get(User, account.user_id)
        if user is not None and not user.is_active:
            raise HTTPException(status_code=403, detail="Inactive user")
    else:
        user = None
        if email:
            user = (await session.exec(select(User).where(User.email == email))).first()
        if user is None:
            user = User(
                email=email or f"{provider_account_id}@{provider}.local",
                full_name=name,
                hashed_password=None,
                is_active=True,
                is_superuser=False,
                # The provider already verified this email address
                is_verified=True,
            )
            session.add(user)
            await session.flush()
        account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_account_id=provider_account_id,
            provider_email=email,
            access_token=token.get("access_token"),
            refresh_token=token.get("refresh_token"),
            expires_at=token.get("expires_at"),
        )
        session.add(account)

    await session.commit()
    if not user:
        raise HTTPException(status_code=500, detail="Failed to resolve user")

    # Create a session (refresh token) so social logins can also refresh
    from app.crud.sessions import create_session as create_auth_session

    refresh_token, _ = await create_auth_session(
        session,
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.id, expires_delta=access_token_expires
    )
    return RedirectResponse(
        url=(
            f"{settings.FRONTEND_HOST}/auth/callback"
            f"?token={access_token}&refresh={refresh_token}"
        )
    )
