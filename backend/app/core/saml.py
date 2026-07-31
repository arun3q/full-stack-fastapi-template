"""Enterprise SAML SSO (python3-saml).

Gated by ``SAML_ENABLED`` + ``SAML_IDP_METADATA`` (a file path or URL to the
IdP's metadata XML). Exposes SP metadata, an SP-initiated login, and the
assertion consumer service (ACS) that provisions the user and starts a session.
"""

import logging
import tempfile
from typing import Any

import httpx
from fastapi import Request
from onelogin.saml2.settings import OneLogin_Saml2_Settings

from app.core.config import settings

logger = logging.getLogger(__name__)


def saml_configured() -> bool:
    return bool(settings.SAML_ENABLED and settings.SAML_IDP_METADATA)


def request_data(
    request: Request, *, post_data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the request dict python3-saml expects from a Starlette request."""
    return {
        "https": request.url.scheme == "https",
        "http_host": request.url.hostname or "",
        "server_port": request.url.port,
        "script_name": request.url.path,
        "get_data": list(request.query_params.multi_items()),
        "post_data": post_data or {},
    }


async def _resolve_idp_metadata() -> str:
    raw = settings.SAML_IDP_METADATA or ""
    if raw.startswith("http://") or raw.startswith("https://"):
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(raw)
            response.raise_for_status()
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as tmp:
            tmp.write(response.text)
            return tmp.name
    return raw


def _settings_dict() -> dict[str, Any]:
    return {
        "strict": True,
        "sp": {
            "entityId": settings.SAML_SP_ENTITY_ID,
            "assertionConsumerService": {
                "url": settings.SAML_SP_ACS_URL,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": settings.SAML_SP_LOGOUT_URL,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": "",
        },
        "security": {
            "wantMessagesSigned": False,
            "wantAssertionsSigned": False,
            "signMetadata": False,
        },
    }


async def build_settings() -> OneLogin_Saml2_Settings:
    idp_path = await _resolve_idp_metadata()
    return OneLogin_Saml2_Settings(
        _settings_dict(),
        idp_metadata_file=idp_path,  # ty: ignore[unknown-argument]
    )


async def metadata_xml() -> str:
    settings_obj = await build_settings()
    return settings_obj.get_sp_metadata()
