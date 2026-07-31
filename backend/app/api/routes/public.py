from fastapi import APIRouter

from app.core.config import settings
from app.models import PublicConfig

router = APIRouter(tags=["public"])


@router.get("/public/config", response_model=PublicConfig)
async def public_config() -> PublicConfig:
    """Public branding/config used by the marketing pages (no auth)."""
    return PublicConfig(
        project_name=settings.PROJECT_NAME,
        support_email=settings.EMAILS_FROM_EMAIL,
    )
