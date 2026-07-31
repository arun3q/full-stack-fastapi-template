import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.access import get_active_plan
from app.models import (
    OrganizationMember,
    Plan,
    Subscription,
    User,
    UserCreate,
)
from tests.utils.utils import random_email, random_lower_string

_EXPECTED_INDEXES = [
    "ix_item_organization_id",
    "ix_session_user_id",
    "ix_session_created_at",
    "ix_organizationmember_user_id",
    "ix_subscription_organization_id",
    "ix_subscription_plan_id",
    "ix_webhookdelivery_webhook_id",
    "ix_webhookdelivery_status",
    "ix_webhookdelivery_next_retry_at",
    "ix_organizationinvite_status",
    "ix_user_created_at",
    "ix_organization_created_at",
    "ix_auditlog_created_at",
]


async def test_missing_indexes_created(db: AsyncSession) -> None:
    rows = (await db.execute(text("SELECT indexname FROM pg_indexes"))).all()
    names = {row[0] for row in rows}
    for index in _EXPECTED_INDEXES:
        assert index in names, f"missing index {index}"


async def test_get_active_plan_returns_plan(db: AsyncSession) -> None:
    email = random_email()
    password = random_lower_string()
    await crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
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

    slug = f"cached-{uuid.uuid4().hex[:8]}"
    plan = Plan(
        name="Cached",
        slug=slug,
        amount_cents=100,
        currency="usd",
        quotas=json.dumps({"ai_calls": 10}),
    )
    db.add(plan)
    await db.flush()
    db.add(
        Subscription(
            organization_id=membership.organization_id,
            plan_id=plan.id,
            provider="stripe",
            status="active",
        )
    )
    await db.commit()

    active = await get_active_plan(db, membership.organization_id)
    assert active is not None
    assert active.slug == slug


def test_validate_webhook_url_ssrf_guard() -> None:
    from app.core.webhooks import validate_webhook_url

    # Valid public URLs pass
    validate_webhook_url("https://example.com/hook")
    validate_webhook_url("http://example.com/hook")

    # Private / metadata / scheme-less URLs are rejected
    import pytest

    with pytest.raises(ValueError):
        validate_webhook_url("169.254.169.254/latest/meta-data")
    with pytest.raises(ValueError):
        validate_webhook_url("https://192.168.1.1/hook")
    with pytest.raises(ValueError):
        validate_webhook_url("https://10.0.0.1/hook")
    with pytest.raises(ValueError):
        validate_webhook_url("ftp://example.com/hook")
