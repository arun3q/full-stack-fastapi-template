"""Social OAuth configuration (Authlib).

Providers are registered at import time only if credentials are configured, so
an unconfigured provider simply won't show up in ``get_configured_providers()``
and its login route returns 404.
"""

import logging
from typing import Any

from authlib.integrations.starlette_client import OAuth

from app.core.config import settings

logger = logging.getLogger(__name__)

oauth = OAuth()

_PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
    "google": {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "server_metadata_url": (
            "https://accounts.google.com/.well-known/openid-configuration"
        ),
        "client_kwargs": {"scope": "openid email profile"},
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
    },
    "linkedin": {
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "access_token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "client_kwargs": {"scope": "openid profile email"},
        "userinfo_url": "https://api.linkedin.com/v2/userinfo",
    },
    "meta": {
        "client_id": settings.META_CLIENT_ID,
        "client_secret": settings.META_CLIENT_SECRET,
        "authorize_url": "https://www.facebook.com/v21.0/dialog/oauth",
        "access_token_url": "https://graph.facebook.com/v21.0/oauth/access_token",
        "client_kwargs": {"scope": "email"},
        "userinfo_url": "https://graph.facebook.com/v21.0/me?fields=id,name,email",
    },
    "github": {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "authorize_url": "https://github.com/login/oauth/authorize",
        "access_token_url": "https://github.com/login/oauth/access_token",
        "api_base_url": "https://api.github.com/",
        "client_kwargs": {"scope": "read:user user:email"},
        "userinfo_url": "https://api.github.com/user",
    },
}

_configured_providers: list[str] = []


def _register_providers() -> None:
    for name, config in _PROVIDER_CONFIGS.items():
        if not config.get("client_id") or not config.get("client_secret"):
            continue
        registration = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "client_kwargs": config.get("client_kwargs", {}),
        }
        for key in (
            "server_metadata_url",
            "authorize_url",
            "access_token_url",
            "api_base_url",
        ):
            if config.get(key):
                registration[key] = config[key]
        oauth.register(name, **registration)
        _configured_providers.append(name)


_register_providers()


def get_configured_providers() -> list[str]:
    return list(_configured_providers)


async def get_provider_userinfo(client: Any, provider: str) -> dict[str, Any]:
    """Fetch normalized ``{id, email, name}`` info for a logged-in provider."""
    config = _PROVIDER_CONFIGS[provider]
    url = config["userinfo_url"]
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()

    if provider == "github":
        emails = []
        try:
            emails_resp = await client.get("https://api.github.com/user/emails")
            emails = emails_resp.json()
        except Exception:
            logger.debug("Could not fetch GitHub emails", exc_info=True)
        email = data.get("email")
        if not email:
            for entry in emails:
                if entry.get("primary") and entry.get("verified"):
                    email = entry.get("email")
                    break
        return {"id": str(data.get("id")), "email": email, "name": data.get("name")}

    return {
        "id": str(data.get("id") or data.get("sub")),
        "email": data.get("email"),
        "name": data.get("name"),
    }
