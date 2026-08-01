import json
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
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


async def _personal_org(db: AsyncSession, email: str) -> str:
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
    return str(membership.organization_id)


async def test_admin_plan_crud(client: TestClient) -> None:
    superuser_headers = _headers(
        _login(client, settings.FIRST_SUPERUSER, settings.FIRST_SUPERUSER_PASSWORD)[
            "access_token"
        ]
    )
    slug = f"custom-{uuid.uuid4().hex[:8]}"
    created = client.post(
        f"{settings.API_V1_STR}/admin/plans",
        headers=superuser_headers,
        json={
            "name": "Custom",
            "slug": slug,
            "amount_cents": 999,
            "currency": "usd",
            "trial_days": 7,
            "provider_plan_id": "price_custom",
        },
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]

    updated = client.patch(
        f"{settings.API_V1_STR}/admin/plans/{plan_id}",
        headers=superuser_headers,
        json={"amount_cents": 1299},
    )
    assert updated.status_code == 200
    assert updated.json()["amount_cents"] == 1299

    deleted = client.delete(
        f"{settings.API_V1_STR}/admin/plans/{plan_id}", headers=superuser_headers
    )
    assert deleted.status_code == 200


async def test_change_plan_rejects_unset_provider_price(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
    org_id = await _personal_org(db, email)
    plan = Plan(
        name="Base",
        slug=f"base-{uuid.uuid4().hex[:8]}",
        amount_cents=100,
        currency="usd",
    )
    db.add(plan)
    await db.flush()
    db.add(
        Subscription(
            organization_id=org_id,
            plan_id=plan.id,
            provider="stripe",
            status="active",
            provider_subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
        )
    )
    await db.commit()

    new_plan = Plan(
        name="NoPrice",
        slug=f"noprice-{uuid.uuid4().hex[:8]}",
        amount_cents=200,
        currency="usd",
    )
    db.add(new_plan)
    await db.commit()

    headers = _headers(_login(client, email, password)["access_token"])
    with patch.object(settings, "PAYMENT_PROVIDER", "stripe"):
        r = client.post(
            f"{settings.API_V1_STR}/payments/change-plan?plan_id={new_plan.id}",
            headers=headers,
        )
    assert r.status_code == 400
    assert "provider price" in r.json()["detail"]


async def test_change_plan_downgrade_rejected_when_over_limits(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
    org_id = await _personal_org(db, email)
    plan = Plan(
        name="Base",
        slug=f"base-{uuid.uuid4().hex[:8]}",
        amount_cents=100,
        currency="usd",
        quotas=json.dumps({"max_items": 10}),
    )
    db.add(plan)
    await db.flush()
    db.add(
        Subscription(
            organization_id=org_id,
            plan_id=plan.id,
            provider="stripe",
            status="active",
            provider_subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
        )
    )
    await db.commit()

    # Create 3 items (over the 1-item limit of the target plan)
    headers = _headers(_login(client, email, password)["access_token"])
    for i in range(3):
        r = client.post(
            f"{settings.API_V1_STR}/items/",
            headers=headers,
            json={"title": f"item {i}", "description": "x"},
        )
        assert r.status_code == 200

    small_plan = Plan(
        name="Small",
        slug=f"small-{uuid.uuid4().hex[:8]}",
        amount_cents=50,
        currency="usd",
        provider_plan_id="price_small",
        quotas=json.dumps({"max_items": 1}),
    )
    db.add(small_plan)
    await db.commit()

    with patch.object(settings, "PAYMENT_PROVIDER", "stripe"):
        r = client.post(
            f"{settings.API_V1_STR}/payments/change-plan?plan_id={small_plan.id}",
            headers=headers,
        )
    assert r.status_code == 400
    assert "item limit" in r.json()["detail"]


async def test_one_active_subscription_db_constraint(db: AsyncSession) -> None:
    email, _ = await _create_user(db)
    org_id = await _personal_org(db, email)
    plan = Plan(
        name="P", slug=f"p-{uuid.uuid4().hex[:8]}", amount_cents=100, currency="usd"
    )
    db.add(plan)
    await db.flush()
    db.add(
        Subscription(
            organization_id=org_id,
            plan_id=plan.id,
            provider="stripe",
            status="active",
        )
    )
    await db.commit()

    import pytest

    with pytest.raises(IntegrityError):
        db.add(
            Subscription(
                organization_id=org_id,
                plan_id=plan.id,
                provider="stripe",
                status="active",
            )
        )
        await db.flush()
    await db.rollback()


async def test_seat_quantity_syncs_locally_on_accept(
    client: TestClient, db: AsyncSession
) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _headers(
        _login(client, owner_email, owner_password)["access_token"]
    )
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()
    plan = Plan(
        name="P", slug=f"p-{uuid.uuid4().hex[:8]}", amount_cents=100, currency="usd"
    )
    db.add(plan)
    await db.flush()
    db.add(
        Subscription(
            organization_id=org["id"],
            plan_id=plan.id,
            provider="stripe",
            status="active",
            quantity=1,
            provider_subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
        )
    )
    await db.commit()

    member_email, member_password = await _create_user(db)
    invite = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members",
        headers=owner_headers,
        json={"email": member_email, "role": "member"},
    ).json()
    from app.models import OrganizationInvite

    token = (
        await db.exec(
            select(OrganizationInvite).where(OrganizationInvite.id == invite["id"])
        )
    ).first()
    assert token is not None
    member_headers = _headers(
        _login(client, member_email, member_password)["access_token"]
    )
    assert (
        client.post(
            f"{settings.API_V1_STR}/organizations/invites/{token.token}/accept",
            headers=member_headers,
        ).status_code
        == 200
    )

    sub = (
        await db.exec(
            select(Subscription).where(Subscription.organization_id == org["id"])
        )
    ).first()
    assert sub is not None
    await db.refresh(sub)
    assert sub.quantity == 2  # no provider configured -> local-only sync
