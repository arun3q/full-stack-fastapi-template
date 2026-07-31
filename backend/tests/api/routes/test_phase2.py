import json
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.core.usage import check_quota, get_usage, record_usage
from app.models import (
    OrganizationMember,
    Plan,
    Subscription,
    UsageEvent,
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


async def _personal_org_id(db: AsyncSession, email: str) -> str:
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


async def _subscribe_org(
    db: AsyncSession, org_id: str, slug: str, quotas: dict
) -> Plan:
    plan = Plan(
        name=slug.title(),
        slug=slug,
        amount_cents=1999,
        currency="usd",
        quotas=json.dumps(quotas),
    )
    db.add(plan)
    await db.flush()
    db.add(
        Subscription(
            organization_id=org_id, plan_id=plan.id, provider="stripe", status="active"
        )
    )
    await db.commit()
    return plan


async def test_usage_quota_enforcement(db: AsyncSession) -> None:
    email, _ = await _create_user(db)
    org_id = await _personal_org_id(db, email)
    slug = f"quota-{uuid.uuid4().hex[:8]}"
    await _subscribe_org(db, org_id, slug, {"ai_calls": 1})

    # Within quota
    assert await check_quota(db, organization_id=org_id, meter="ai_calls", amount=1)
    await record_usage(db, organization_id=org_id, meter="ai_calls", amount=1)
    await db.commit()

    # Exceeded
    assert not await check_quota(db, organization_id=org_id, meter="ai_calls", amount=1)
    assert await get_usage(db, organization_id=org_id, meter="ai_calls") == 1


async def test_usage_events_recorded(db: AsyncSession) -> None:
    email, _ = await _create_user(db)
    org_id = await _personal_org_id(db, email)
    await record_usage(db, organization_id=org_id, meter="ai_calls", amount=3)
    await db.commit()
    events = (
        await db.exec(
            select(UsageEvent).where(
                UsageEvent.organization_id == org_id,
                UsageEvent.meter == "ai_calls",
            )
        )
    ).all()
    assert sum(e.amount for e in events) == 3


async def test_single_active_subscription_guard(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
    org_id = await _personal_org_id(db, email)
    slug = f"guard-{uuid.uuid4().hex[:8]}"
    await _subscribe_org(db, org_id, slug, {})

    headers = _headers(_login(client, email, password)["access_token"])
    plan = (await db.exec(select(Plan).where(Plan.slug == slug))).first()
    assert plan is not None
    with patch.object(settings, "PAYMENT_PROVIDER", "stripe"):
        r = client.post(
            f"{settings.API_V1_STR}/payments/checkout?plan_id={plan.id}",
            headers=headers,
        )
        assert r.status_code == 409


async def test_change_plan_unconfigured(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    headers = _headers(_login(client, email, password)["access_token"])
    plan_id = uuid.uuid4()
    r = client.post(
        f"{settings.API_V1_STR}/payments/change-plan?plan_id={plan_id}",
        headers=headers,
    )
    assert r.status_code == 503


async def test_admin_overview_includes_mrr(
    client: TestClient, db: AsyncSession
) -> None:
    email, _ = await _create_user(db)
    org_id = await _personal_org_id(db, email)
    slug = f"mrr-{uuid.uuid4().hex[:8]}"
    await _subscribe_org(db, org_id, slug, {})

    superuser_headers = _headers(
        _login(client, settings.FIRST_SUPERUSER, settings.FIRST_SUPERUSER_PASSWORD)[
            "access_token"
        ]
    )
    r = client.get(f"{settings.API_V1_STR}/admin/overview", headers=superuser_headers)
    assert r.status_code == 200
    assert r.json()["mrr_cents"] >= 1999
