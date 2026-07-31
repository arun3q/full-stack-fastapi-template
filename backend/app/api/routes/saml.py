from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from sqlmodel import select

from app.api.deps import SessionDep
from app.core import security
from app.core.audit import audit_event
from app.core.config import settings
from app.core.saml import (
    build_settings,
    metadata_xml,
    request_data,
    saml_configured,
)
from app.models import Message, User

router = APIRouter(prefix="/auth/saml", tags=["saml"])


def _require_saml() -> None:
    if not saml_configured():
        raise HTTPException(status_code=503, detail="SAML SSO is not configured")


@router.get("/metadata")
async def saml_metadata() -> Response:
    """SP metadata XML for your IdP."""
    _require_saml()
    xml = await metadata_xml()
    return Response(content=xml, media_type="application/xml")


@router.get("/login")
async def saml_login(request: Request) -> RedirectResponse:
    """SP-initiated login: redirect to the IdP."""
    _require_saml()
    auth = OneLogin_Saml2_Auth(request_data(request), await build_settings())
    url = auth.login()
    return RedirectResponse(url=url)


@router.post("/acs")
async def saml_acs(request: Request, session: SessionDep) -> RedirectResponse:
    """Assertion Consumer Service: validate the assertion and log the user in."""
    _require_saml()
    form = await request.form()
    auth = OneLogin_Saml2_Auth(
        request_data(request, post_data=dict(form.multi_items())),
        await build_settings(),
    )
    auth.process_response()
    if auth.get_errors():
        raise HTTPException(
            status_code=400, detail=f"SAML error: {', '.join(auth.get_errors())}"
        )

    email = str(auth.get_nameid() or "").lower()
    attributes = auth.get_attributes()
    if not email:
        email_attr = attributes.get(settings.SAML_ATTRIBUTE_EMAIL, [])
        email = str(email_attr[0]).lower() if email_attr else ""
    if not email:
        raise HTTPException(status_code=400, detail="No email in SAML assertion")

    name_attr = attributes.get(settings.SAML_ATTRIBUTE_NAME, [])
    full_name = str(name_attr[0]) if name_attr else None

    user = (await session.exec(select(User).where(User.email == email))).first()
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=None,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
    else:
        if full_name:
            user.full_name = full_name
        session.add(user)
    await session.commit()

    await audit_event(
        action="auth.saml_login",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        user.id, expires_delta=access_token_expires
    )
    url = f"{settings.FRONTEND_HOST}/auth/callback?token={access_token}"
    response = RedirectResponse(url=url)
    if settings.AUTH_TOKEN_IN_COOKIE:
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=settings.ENVIRONMENT != "local",
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    return response


@router.get("/status", response_model=Message)
async def saml_status() -> Message:
    """Whether SAML SSO is configured."""
    return Message(message="configured" if saml_configured() else "not-configured")
