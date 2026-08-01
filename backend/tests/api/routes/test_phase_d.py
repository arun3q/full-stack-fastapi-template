from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.models import Item, UserCreate
from tests.utils.utils import random_email, random_lower_string


def _login(client: TestClient, email: str, password: str) -> dict:
    return client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    ).json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_email_uniqueness_is_case_insensitive(
    client: TestClient, db: AsyncSession
) -> None:
    email = random_email()
    password = random_lower_string()
    await crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )

    # Same email with different case must be rejected at the DB level
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await crud.create_user(
            session=db,
            user_create=UserCreate(email=email.upper(), password=random_lower_string()),
        )
    await db.rollback()


async def test_org_delete_cascades_tenant_data(
    client: TestClient, db: AsyncSession
) -> None:
    email = random_email()
    password = random_lower_string()
    await crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
    headers = _headers(_login(client, email, password)["access_token"])
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=headers,
        json={"name": "Acme"},
    ).json()

    # Create an item in the org
    item = client.post(
        f"{settings.API_V1_STR}/items/",
        headers=headers,
        json={"title": "tenant item", "description": "x"},
    ).json()

    # Delete the org (GDPR)
    r = client.delete(f"{settings.API_V1_STR}/organizations/{org['id']}", headers=headers)
    assert r.status_code == 200

    # The item must be gone (cascade), not orphaned
    assert await db.get(Item, item["id"]) is None


async def test_check_constraints_exist(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conname IN ('ck_orgmember_role','ck_subscription_status',"
                "'ck_plan_amount_nonneg','ck_subscription_quantity_pos',"
                "'ck_usageevent_amount_pos','ck_user_role')"
            )
        )
    ).all()
    names = {row[0] for row in rows}
    assert "ck_orgmember_role" in names
    assert "ck_subscription_status" in names
    assert "ck_plan_amount_nonneg" in names


async def test_email_lower_unique_index(db: AsyncSession) -> None:
    rows = (
        await db.execute(
            text("SELECT indexname FROM pg_indexes WHERE indexname = 'uq_user_email_lower'")
        )
    ).all()
    assert len(rows) == 1
