from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.models import ORG_ROLE_MEMBER, OrganizationMember, User, UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


async def _create_key_headers(client: TestClient, db: AsyncSession) -> dict[str, str]:
    email = random_email()
    password = random_lower_string()
    await crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
    headers = user_authentication_headers(client=client, email=email, password=password)
    key = client.post(
        f"{settings.API_V1_STR}/api-keys/",
        headers=headers,
        json={"name": "scim", "scopes": ["scim"]},
    ).json()["key"]
    return {"Authorization": f"Bearer {key}"}


def test_scim_requires_token(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/scim/v2/Users")
    assert r.status_code == 401


async def test_scim_provision_user(client: TestClient, db: AsyncSession) -> None:
    scim_headers = await _create_key_headers(client, db)
    email = random_email()

    created = client.post(
        f"{settings.API_V1_STR}/scim/v2/Users",
        headers=scim_headers,
        json={"userName": email, "displayName": "SCIM User", "active": True},
    )
    assert created.status_code == 201
    assert created.json()["userName"] == email
    user_id = created.json()["id"]

    # The user now exists and is a member of the key's organization
    user = (await db.exec(select(User).where(User.email == email))).first()
    assert user is not None
    assert user.is_active is True

    listing = client.get(f"{settings.API_V1_STR}/scim/v2/Users", headers=scim_headers)
    assert listing.status_code == 200
    assert listing.json()["totalResults"] >= 1

    # Deactivate via PATCH
    patched = client.patch(
        f"{settings.API_V1_STR}/scim/v2/Users/{user_id}",
        headers=scim_headers,
        json={"active": False},
    )
    assert patched.status_code == 200
    assert patched.json()["active"] is False

    # SCIM delete == deactivate (scoped to this org's membership only)
    deleted = client.delete(
        f"{settings.API_V1_STR}/scim/v2/Users/{user_id}",
        headers=scim_headers,
    )
    assert deleted.status_code == 204
    user = (await db.exec(select(User).where(User.email == email))).first()
    assert user is not None
    await db.refresh(user)
    assert user.is_active is True  # platform account untouched
    membership = (
        await db.exec(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.role == ORG_ROLE_MEMBER,
            )
        )
    ).first()
    assert membership is not None
    assert membership.active is False


async def test_scim_groups(client: TestClient, db: AsyncSession) -> None:
    scim_headers = await _create_key_headers(client, db)
    r = client.get(f"{settings.API_V1_STR}/scim/v2/Groups", headers=scim_headers)
    assert r.status_code == 200
    assert r.json()["totalResults"] >= 1
