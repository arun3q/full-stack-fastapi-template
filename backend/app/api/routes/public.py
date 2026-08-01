from fastapi import APIRouter, Response

from app.core.cache import cached
from app.core.config import settings
from app.models import PublicConfig

router = APIRouter(tags=["public"])


@router.get("/public/config", response_model=PublicConfig)
@cached(lambda *args, **kwargs: "public_config", ttl_seconds=300)
async def public_config(
    response: Response,
) -> PublicConfig:
    """Public branding/config used by the marketing pages (no auth)."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return PublicConfig(
        project_name=settings.PROJECT_NAME,
        support_email=settings.EMAILS_FROM_EMAIL,
    )
