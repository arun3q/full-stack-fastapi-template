import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.core.jobs import (
    requeue_stale_webhook_deliveries_job,
    subscription_dunning_job,
)
from app.models import (
    Notification,
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


async def test_viewer_cannot_cancel_subscription(
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

    viewer_email, viewer_password = await _create_user(db)
    viewer = (await db.exec(select(User).where(User.email == viewer_email))).first()
    assert viewer is not None
    db.add(
        OrganizationMember(organization_id=org["id"], user_id=viewer.id, role="viewer")
    )
    await db.commit()

    viewer_headers = _headers(
        _login(client, viewer_email, viewer_password)["access_token"]
    )
    r = client.post(
        f"{settings.API_V1_STR}/payments/subscription/cancel",
        headers=viewer_headers,
    )
    assert r.status_code == 403


async def test_viewer_cannot_create_api_key(
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

    member_email, member_password = await _create_user(db)
    member = (await db.exec(select(User).where(User.email == member_email))).first()
    assert member is not None
    db.add(
        OrganizationMember(organization_id=org["id"], user_id=member.id, role="viewer")
    )
    await db.commit()

    member_headers = _headers(
        _login(client, member_email, member_password)["access_token"]
    )
    r = client.post(
        f"{settings.API_V1_STR}/api-keys/",
        headers=member_headers,
        json={"name": "nope", "scopes": ["read"]},
    )
    assert r.status_code == 403


async def test_dunning_job_notifies_past_due_owner(
    _client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
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
        name="Pro", slug=f"pro-{uuid.uuid4().hex[:8]}", amount_cents=100, currency="usd"
    )
    db.add(plan)
    await db.flush()
    db.add(
        Subscription(
            organization_id=membership.organization_id,
            plan_id=plan.id,
            provider="stripe",
            status="past_due",
        )
    )
    await db.commit()

    with patch("app.core.jobs.maintenance.send_email_background"):
        await subscription_dunning_job({})

    notification = (
        await db.exec(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.type == "billing",
            )
        )
    ).first()
    assert notification is not None
    assert "past due" in notification.title.lower()


async def test_requeue_stale_webhook_deliveries(
    _client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
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

    from datetime import UTC, datetime, timedelta

    webhook = await crud.create_webhook(
        db,
        organization_id=membership.organization_id,
        url="https://example.com/hook",
        secret="secret",
        events=["*"],
    )
    delivery = await crud.create_delivery(
        db,
        webhook_id=webhook.id,
        event="test",
        payload="{}",
    )
    delivery.status = "pending"
    delivery.attempts = 1
    delivery.next_retry_at = datetime.now(UTC) - timedelta(minutes=5)
    db.add(delivery)
    await db.commit()

    with patch(
        "app.core.jobs.maintenance.enqueue_job", return_value="job-1"
    ) as enqueue:
        await requeue_stale_webhook_deliveries_job({})
        assert enqueue.called


async def test_csrf_protection_cookie_mode(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
    with patch.object(settings, "AUTH_TOKEN_IN_COOKIE", True):
        login = client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": email, "password": password},
        )
        assert login.status_code == 200
        csrf_token = login.cookies.get("csrf_token")
        access_cookie = login.cookies.get("access_token")
        assert csrf_token and access_cookie

        # Without the CSRF header -> 403
        r = client.post(
            f"{settings.API_V1_STR}/users/me/password",
            cookies={"access_token": access_cookie, "csrf_token": csrf_token},
            json={
                "current_password": password,
                "new_password": random_lower_string(),
            },
        )
        assert r.status_code == 403

        # With the CSRF header -> not a CSRF rejection
        r = client.post(
            f"{settings.API_V1_STR}/users/me/password",
            cookies={"access_token": access_cookie, "csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
            json={
                "current_password": password,
                "new_password": random_lower_string(),
            },
        )
        assert r.status_code != 403


def test_readiness_endpoint(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/utils/ready")
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "degraded")


def test_health_check_requires_db(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    assert r.status_code == 200
    assert r.json() is True
