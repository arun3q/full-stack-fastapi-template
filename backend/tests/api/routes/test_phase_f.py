import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.models import OrganizationMember, Plan, Subscription, User, UserCreate
from tests.utils.utils import random_email, random_lower_string


async def _create_user(db: AsyncSession) -> tuple[str, str]:
    email = random_email()
    password = random_lower_string()
    await crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
    return email, password


def _login(client: TestClient, email: str, password: str) -> dict:
    return client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    ).json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_payments_usage_endpoint(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    headers = _headers(_login(client, email, password)["access_token"])
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=headers,
        json={"name": "Acme"},
    ).json()

    r = client.get(f"{settings.API_V1_STR}/payments/usage", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "ai_calls" in data
    assert isinstance(data["ai_calls"], dict)
    assert "used" in data["ai_calls"] and "limit" in data["ai_calls"]


async def test_razorpay_statuses_allowed_by_check(
    client: TestClient, db: AsyncSession
) -> None:
    """The subscription status CHECK must accept Razorpay's completed/halted/pending."""
    email, _ = await _create_user(db)
    user = (await db.exec(select(User).where(User.email == email))).first()
    assert user is not None
    membership = (
        await db.exec(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.role == "owner",
            )
        )
    ).first()
    assert membership is not None

    plan = Plan(
        name="P", slug=f"p-{uuid.uuid4().hex[:8]}", amount_cents=100, currency="usd"
    )
    db.add(plan)
    await db.flush()
    for status in ("completed", "halted", "pending"):
        db.add(
            Subscription(
                organization_id=membership.organization_id,
                plan_id=plan.id,
                provider="razorpay",
                status=status,
            )
        )
        await db.flush()  # must not raise IntegrityError
    await db.rollback()
