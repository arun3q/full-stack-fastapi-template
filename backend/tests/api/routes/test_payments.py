import uuid

from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import Plan


async def test_read_plans(
    client: TestClient, superuser_token_headers: dict[str, str], db: AsyncSession
) -> None:
    plan = Plan(
        name="Test Plan",
        slug=f"test-{uuid.uuid4()}",
        amount_cents=100,
        currency="usd",
    )
    db.add(plan)
    await db.commit()

    r = client.get(
        f"{settings.API_V1_STR}/payments/plans",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    content = r.json()
    assert content["count"] >= 1
    assert all("amount_cents" in p for p in content["data"])


async def test_checkout_not_configured(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/payments/checkout?plan_id={uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 503


async def test_webhook_not_configured(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/payments/webhook",
        headers=superuser_token_headers,
        json={"event": "subscription.activated"},
    )
    assert r.status_code == 503


async def test_read_subscription_empty(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/payments/subscription",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    assert r.json() is None


async def test_cancel_subscription_no_active(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/payments/subscription/cancel",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 503 or r.status_code == 404
