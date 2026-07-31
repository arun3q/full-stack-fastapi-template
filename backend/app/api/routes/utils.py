from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr
from sqlmodel import select

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.jobs import send_email_background
from app.core.redis import redis_client
from app.models import Message
from app.utils import generate_test_email

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
async def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    await send_email_background(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/")
async def health_check(session: SessionDep) -> bool:
    """Liveness: returns true when the database is reachable."""
    await session.exec(select(1))
    return True


@router.get("/ready")
async def readiness(session: SessionDep) -> dict[str, str]:
    """Readiness: checks the database and Redis (best-effort)."""
    await session.exec(select(1))
    redis_ok = True
    try:
        await redis_client.ping()
    except Exception:
        redis_ok = False
    status = "ok" if redis_ok else "degraded"
    return {"status": status, "redis": "ok" if redis_ok else "down"}
