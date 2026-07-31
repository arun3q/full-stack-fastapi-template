from fastapi import APIRouter

from app.core.cache import cached
from app.core.config import settings
from app.models import PublicConfig

router = APIRouter(tags=["public"])


@router.get("/public/config", response_model=PublicConfig)
@cached(lambda *args, **kwargs: "public_config", ttl_seconds=300)
async def public_config() -> PublicConfig:
    """Public branding/config used by the marketing pages (no auth)."""
    return PublicConfig(
        project_name=settings.PROJECT_NAME,
        support_email=settings.EMAILS_FROM_EMAIL,
    )
