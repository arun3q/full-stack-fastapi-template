from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.models import (
    OrganizationMember,
    Plan,
    Subscription,
    User,
    UserCreate,
)
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


async def _create_user(
    db: AsyncSession, *, role: str = "user", password: str | None = None
) -> tuple[str, str]:
    email = random_email()
    password = password or random_lower_string()
    user_in = UserCreate(email=email, password=password, role=role)
    await crud.create_user(session=db, user_create=user_in)
    return email, password


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    return user_authentication_headers(client=client, email=email, password=password)


async def _subscribe(db: AsyncSession, email: str, slug: str = "pro") -> None:
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
    plan = (await db.exec(select(Plan).where(Plan.slug == slug))).first()
    if plan is None:
        plan = Plan(
            name=slug.title(),
            slug=slug,
            amount_cents=1999,
            currency="usd",
        )
        db.add(plan)
        await db.flush()
    subscription = Subscription(
        organization_id=membership.organization_id,
        plan_id=plan.id,
        provider="stripe",
        status="active",
    )
    db.add(subscription)
    await db.commit()


async def test_user_access_me(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    headers = _login(client, email, password)
    r = client.get(f"{settings.API_V1_STR}/users/me/access", headers=headers)
    assert r.status_code == 200
    content = r.json()
    assert content["role"] == "user"
    assert content["is_superuser"] is False
    assert content["is_verified"] is False
    assert content["plan"] is None
    assert "items:create" in content["features"]
    # billing is disabled by default -> nothing is gated
    assert "ai:chat" in content["features"]


async def test_role_admin_can_access_admin_endpoints(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db, role="admin")
    headers = _login(client, email, password)
    r = client.get(f"{settings.API_V1_STR}/users/", headers=headers)
    assert r.status_code == 200


async def test_role_staff_cannot_access_admin_endpoints(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db, role="staff")
    headers = _login(client, email, password)
    r = client.get(f"{settings.API_V1_STR}/users/", headers=headers)
    assert r.status_code == 403


async def test_staff_can_view_all_items(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db, role="staff")
    headers = _login(client, email, password)
    r = client.get(f"{settings.API_V1_STR}/items/all", headers=headers)
    assert r.status_code == 200


async def test_normal_user_cannot_view_all_items(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
    headers = _login(client, email, password)
    r = client.get(f"{settings.API_V1_STR}/items/all", headers=headers)
    assert r.status_code == 403


async def test_ai_chat_requires_paid_plan(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    headers = _login(client, email, password)
    body = {"messages": [{"role": "user", "content": "hi"}]}
    with patch.object(settings, "PAYMENT_PROVIDER", "stripe"):
        r = client.post(f"{settings.API_V1_STR}/ai/chat", headers=headers, json=body)
        assert r.status_code == 403
        assert "plan" in r.json()["detail"]

        # Free user subscribes to Pro -> gate passes, but no AI provider configured
        await _subscribe(db, email, "pro")
        r = client.post(f"{settings.API_V1_STR}/ai/chat", headers=headers, json=body)
        assert r.status_code == 503


async def test_admin_bypasses_plan_gate(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db, role="admin")
    headers = _login(client, email, password)
    body = {"messages": [{"role": "user", "content": "hi"}]}
    with patch.object(settings, "PAYMENT_PROVIDER", "stripe"):
        r = client.post(f"{settings.API_V1_STR}/ai/chat", headers=headers, json=body)
        assert r.status_code == 503


async def test_free_plan_item_quota(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    headers = _login(client, email, password)
    with patch.object(settings, "PAYMENT_PROVIDER", "stripe"):
        for i in range(5):
            r = client.post(
                f"{settings.API_V1_STR}/items/",
                headers=headers,
                json={"title": f"Item {i}"},
            )
            assert r.status_code == 200
        r = client.post(
            f"{settings.API_V1_STR}/items/",
            headers=headers,
            json={"title": "Too many"},
        )
        assert r.status_code == 403

        await _subscribe(db, email, "pro")
        r = client.post(
            f"{settings.API_V1_STR}/items/",
            headers=headers,
            json={"title": "Now allowed"},
        )
        assert r.status_code == 200
