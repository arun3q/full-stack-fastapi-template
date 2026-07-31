from fastapi import APIRouter
from fastapi.responses import Response

from app.core.config import settings

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint (scrape by your monitoring stack)."""
    if not settings.ENABLE_METRICS:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Metrics disabled")
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
