from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.models import (
    ORG_ROLE_MEMBER,
    OrganizationMember,
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


async def _org_with_admin(client: TestClient, db: AsyncSession) -> tuple[dict, str, str]:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _headers(_login(client, owner_email, owner_password)["access_token"])
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()

    admin_email, admin_password = await _create_user(db)
    invite = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members",
        headers=owner_headers,
        json={"email": admin_email, "role": "admin"},
    ).json()
    from app.models import OrganizationInvite

    token = (
        await db.exec(
            select(OrganizationInvite).where(OrganizationInvite.id == invite["id"])
        )
    ).first()
    assert token is not None
    admin_headers = _headers(_login(client, admin_email, admin_password)["access_token"])
    assert (
        client.post(
            f"{settings.API_V1_STR}/organizations/invites/{token.token}/accept",
            headers=admin_headers,
        ).status_code
        == 200
    )
    admin_user = (await db.exec(select(User).where(User.email == admin_email))).first()
    assert admin_user is not None
    return org, admin_email, admin_password


async def test_admin_cannot_demote_last_owner(
    client: TestClient, db: AsyncSession
) -> None:
    org, admin_email, admin_password = await _org_with_admin(client, db)
    owner_membership = (
        await db.exec(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org["id"],
                OrganizationMember.role == "owner",
            )
        )
    ).first()
    assert owner_membership is not None

    admin_headers = _headers(_login(client, admin_email, admin_password)["access_token"])
    r = client.patch(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members/{owner_membership.user_id}?role=member",
        headers=admin_headers,
    )
    assert r.status_code == 403  # owner management requires member:remove


async def test_invite_rejects_owner_role(client: TestClient, db: AsyncSession) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _headers(_login(client, owner_email, owner_password)["access_token"])
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()
    r = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members",
        headers=owner_headers,
        json={"email": random_email(), "role": "owner"},
    )
    assert r.status_code == 400


async def test_scim_requires_scim_scope(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    headers = _headers(_login(client, email, password)["access_token"])
    key = client.post(
        f"{settings.API_V1_STR}/api-keys/",
        headers=headers,
        json={"name": "noscope", "scopes": ["read"]},
    ).json()["key"]
    r = client.get(
        f"{settings.API_V1_STR}/scim/v2/Users",
        headers={"Authorization": f"Bearer {key}"},
    )
    assert r.status_code == 403


async def test_suspended_org_blocks_org_operations(
    client: TestClient, db: AsyncSession
) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _headers(_login(client, owner_email, owner_password)["access_token"])
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()
    assert (
        client.post(
            f"{settings.API_V1_STR}/organizations/{org['id']}/suspend",
            headers=owner_headers,
        ).status_code
        == 200
    )
    r = client.get(
        f"{settings.API_V1_STR}/organizations/{org['id']}/export",
        headers=owner_headers,
    )
    assert r.status_code == 403


async def test_password_change_revokes_sessions(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
    tokens = _login(client, email, password)
    new_password = random_lower_string()
    headers = _headers(tokens["access_token"])
    r = client.patch(
        f"{settings.API_V1_STR}/users/me/password",
        headers=headers,
        json={
            "current_password": password,
            "new_password": new_password,
        },
    )
    assert r.status_code == 200

    # Old refresh token must no longer work
    r = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert r.status_code == 401


async def test_deactivated_user_refresh_blocked(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
    tokens = _login(client, email, password)

    superuser_headers = _headers(
        _login(client, settings.FIRST_SUPERUSER, settings.FIRST_SUPERUSER_PASSWORD)[
            "access_token"
        ]
    )
    user = (await db.exec(select(User).where(User.email == email))).first()
    assert user is not None
    r = client.patch(
        f"{settings.API_V1_STR}/admin/users/{user.id}/status?is_active=false",
        headers=superuser_headers,
    )
    assert r.status_code == 200

    r = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert r.status_code == 401


async def test_delete_account_blocked_when_owner_of_org_with_members(
    client: TestClient, db: AsyncSession
) -> None:
    fresh_email, fresh_password = await _create_user(db)
    fresh_headers = _headers(_login(client, fresh_email, fresh_password)["access_token"])
    fresh_org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=fresh_headers,
        json={"name": "Acme"},
    ).json()
    member_email, member_password = await _create_user(db)
    invite = client.post(
        f"{settings.API_V1_STR}/organizations/{fresh_org['id']}/members",
        headers=fresh_headers,
        json={"email": member_email, "role": ORG_ROLE_MEMBER},
    ).json()
    from app.models import OrganizationInvite

    token = (
        await db.exec(
            select(OrganizationInvite).where(OrganizationInvite.id == invite["id"])
        )
    ).first()
    assert token is not None
    member_headers = _headers(_login(client, member_email, member_password)["access_token"])
    assert (
        client.post(
            f"{settings.API_V1_STR}/organizations/invites/{token.token}/accept",
            headers=member_headers,
        ).status_code
        == 200
    )
    r = client.delete(f"{settings.API_V1_STR}/users/me", headers=fresh_headers)
    assert r.status_code == 400
