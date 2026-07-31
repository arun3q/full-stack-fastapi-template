from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response

from app.core.config import settings

router = APIRouter(tags=["metrics"])


async def _require_metrics_token(
    authorization: str | None = Header(default=None),
) -> None:
    if not settings.METRICS_TOKEN:
        return
    expected = f"Bearer {settings.METRICS_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid metrics token")


@router.get("/metrics", dependencies=[Depends(_require_metrics_token)])
async def metrics() -> Response:
    """Prometheus metrics endpoint (protected by METRICS_TOKEN when set)."""
    if not settings.ENABLE_METRICS:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
