from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.models import (
    INVITE_CANCELED,
    Organization,
    OrganizationInvite,
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


async def _create_org_with_member(
    client: TestClient, db: AsyncSession
) -> tuple[dict, str, str, str, str]:
    """Create an org (owner) + add a member. Returns (org, owner_email, owner_pw, member_email, member_pw)."""
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
    invite = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members",
        headers=owner_headers,
        json={"email": member_email},
    ).json()
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
    return org, owner_email, owner_password, member_email, member_password


async def test_suspend_organization_blocks_access(
    client: TestClient, db: AsyncSession
) -> None:
    (
        org,
        owner_email,
        owner_password,
        member_email,
        member_password,
    ) = await _create_org_with_member(client, db)
    owner_headers = _headers(
        _login(client, owner_email, owner_password)["access_token"]
    )
    r = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/suspend",
        headers=owner_headers,
    )
    assert r.status_code == 200

    member_headers = _headers(
        _login(client, member_email, member_password)["access_token"]
    )
    r = client.get(f"{settings.API_V1_STR}/items/", headers=member_headers)
    assert r.status_code == 403


async def test_delete_organization(client: TestClient, db: AsyncSession) -> None:
    org, owner_email, owner_password, _, _ = await _create_org_with_member(client, db)
    owner_headers = _headers(
        _login(client, owner_email, owner_password)["access_token"]
    )
    r = client.delete(
        f"{settings.API_V1_STR}/organizations/{org['id']}", headers=owner_headers
    )
    assert r.status_code == 200
    assert await db.get(Organization, org["id"]) is None


async def test_export_organization(client: TestClient, db: AsyncSession) -> None:
    org, owner_email, owner_password, _, _ = await _create_org_with_member(client, db)
    owner_headers = _headers(
        _login(client, owner_email, owner_password)["access_token"]
    )
    r = client.get(
        f"{settings.API_V1_STR}/organizations/{org['id']}/export",
        headers=owner_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["organization"]["name"] == "Acme"
    assert len(data["members"]) >= 1


async def test_revoke_invite(client: TestClient, db: AsyncSession) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _headers(
        _login(client, owner_email, owner_password)["access_token"]
    )
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()

    invite = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members",
        headers=owner_headers,
        json={"email": random_email()},
    ).json()
    r = client.delete(
        f"{settings.API_V1_STR}/organizations/{org['id']}/invites/{invite['id']}",
        headers=owner_headers,
    )
    assert r.status_code == 200
    invite_row = await db.get(OrganizationInvite, invite["id"])
    assert invite_row is not None
    assert invite_row.status == INVITE_CANCELED


async def test_transfer_ownership(client: TestClient, db: AsyncSession) -> None:
    org, owner_email, owner_password, member_email, _ = await _create_org_with_member(
        client, db
    )
    owner_headers = _headers(
        _login(client, owner_email, owner_password)["access_token"]
    )
    member = (await db.exec(select(User).where(User.email == member_email))).first()
    assert member is not None

    r = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/transfer-ownership?user_id={member.id}",
        headers=owner_headers,
    )
    assert r.status_code == 200

    member_row = (
        await db.exec(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org["id"],
                OrganizationMember.user_id == member.id,
            )
        )
    ).first()
    assert member_row is not None
    assert member_row.role == "owner"


async def test_leave_organization_member(client: TestClient, db: AsyncSession) -> None:
    (
        org,
        owner_email,
        owner_password,
        member_email,
        member_password,
    ) = await _create_org_with_member(client, db)
    member_headers = _headers(
        _login(client, member_email, member_password)["access_token"]
    )
    r = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/leave",
        headers=member_headers,
    )
    assert r.status_code == 200
    member = (await db.exec(select(User).where(User.email == member_email))).first()
    assert member is not None
    membership = (
        await db.exec(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org["id"],
                OrganizationMember.user_id == member.id,
            )
        )
    ).first()
    assert membership is None


async def test_owner_cannot_leave_alone(client: TestClient, db: AsyncSession) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _headers(
        _login(client, owner_email, owner_password)["access_token"]
    )
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()
    r = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/leave",
        headers=owner_headers,
    )
    assert r.status_code == 400


async def test_cross_tenant_org_operations_blocked(
    client: TestClient, db: AsyncSession
) -> None:
    """Users must not be able to suspend/delete/export another tenant's org."""
    attacker_email, attacker_password = await _create_user(db)
    attacker_headers = _headers(
        _login(client, attacker_email, attacker_password)["access_token"]
    )

    victim_email, victim_password = await _create_user(db)
    victim_headers = _headers(
        _login(client, victim_email, victim_password)["access_token"]
    )
    victim_org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=victim_headers,
        json={"name": "Victim"},
    ).json()

    # Attacker operates with their own org in the header, targeting the victim's id
    r = client.post(
        f"{settings.API_V1_STR}/organizations/{victim_org['id']}/suspend",
        headers=attacker_headers,
    )
    assert r.status_code == 403

    r = client.get(
        f"{settings.API_V1_STR}/organizations/{victim_org['id']}/export",
        headers=attacker_headers,
    )
    assert r.status_code == 403

    r = client.delete(
        f"{settings.API_V1_STR}/organizations/{victim_org['id']}",
        headers=attacker_headers,
    )
    assert r.status_code == 403

    victim_row = await db.get(Organization, victim_org["id"])
    assert victim_row is not None
    assert victim_row.is_active
