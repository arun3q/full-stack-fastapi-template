from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.models import OrganizationInvite, UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


async def _create_user(
    db: AsyncSession, *, password: str | None = None
) -> tuple[str, str]:
    email = random_email()
    password = password or random_lower_string()
    await crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
    return email, password


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    return user_authentication_headers(client=client, email=email, password=password)


async def test_personal_organization_auto_created(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
    headers = _login(client, email, password)
    r = client.get(f"{settings.API_V1_STR}/organizations/", headers=headers)
    assert r.status_code == 200
    content = r.json()
    assert content["count"] == 1
    assert content["data"][0]["role"] == "owner"


async def test_create_organization(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    headers = _login(client, email, password)
    r = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=headers,
        json={"name": "Acme Inc"},
    )
    assert r.status_code == 200
    org = r.json()
    assert org["name"] == "Acme Inc"
    assert "slug" in org

    # The creator is the owner and now has two organizations
    r = client.get(f"{settings.API_V1_STR}/organizations/", headers=headers)
    assert r.json()["count"] == 2


async def test_update_organization_owner_only(
    client: TestClient, db: AsyncSession
) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _login(client, owner_email, owner_password)
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()

    r = client.patch(
        f"{settings.API_V1_STR}/organizations/{org['id']}",
        headers=owner_headers,
        json={"name": "Acme Corp"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Acme Corp"


async def test_invite_and_accept_flow(client: TestClient, db: AsyncSession) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _login(client, owner_email, owner_password)
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()

    invitee_email, invitee_password = await _create_user(db)

    r = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members",
        headers=owner_headers,
        json={"email": invitee_email},
    )
    assert r.status_code == 200
    invite_id = r.json()["id"]

    invite = (
        await db.exec(
            select(OrganizationInvite).where(OrganizationInvite.id == invite_id)
        )
    ).first()
    assert invite is not None

    invitee_headers = _login(client, invitee_email, invitee_password)
    r = client.post(
        f"{settings.API_V1_STR}/organizations/invites/{invite.token}/accept",
        headers=invitee_headers,
    )
    assert r.status_code == 200

    # The invitee can now list the org's members
    r = client.get(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members",
        headers=invitee_headers,
    )
    assert r.status_code == 200
    assert r.json()["count"] == 2


async def test_invite_wrong_email_rejected(
    client: TestClient, db: AsyncSession
) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _login(client, owner_email, owner_password)
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()

    invitee_email, invitee_password = await _create_user(db)
    intruder_email, intruder_password = await _create_user(db)

    invite = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members",
        headers=owner_headers,
        json={"email": invitee_email},
    ).json()

    token = (
        await db.exec(
            select(OrganizationInvite).where(OrganizationInvite.id == invite["id"])
        )
    ).first()
    assert token is not None

    intruder_headers = _login(client, intruder_email, intruder_password)
    r = client.post(
        f"{settings.API_V1_STR}/organizations/invites/{token.token}/accept",
        headers=intruder_headers,
    )
    assert r.status_code == 403


async def test_member_cannot_invite(client: TestClient, db: AsyncSession) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _login(client, owner_email, owner_password)
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

    member_headers = _login(client, member_email, member_password)
    assert (
        client.post(
            f"{settings.API_V1_STR}/organizations/invites/{token.token}/accept",
            headers=member_headers,
        ).status_code
        == 200
    )

    # A plain member lacks the member:invite permission
    other_email = random_email()
    r = client.post(
        f"{settings.API_V1_STR}/organizations/{org['id']}/members",
        headers=member_headers,
        json={"email": other_email},
    )
    assert r.status_code == 403


async def test_items_scoped_to_organization(
    client: TestClient, db: AsyncSession
) -> None:
    a_email, a_password = await _create_user(db)
    a_headers = _login(client, a_email, a_password)
    b_email, b_password = await _create_user(db)
    b_headers = _login(client, b_email, b_password)

    created = client.post(
        f"{settings.API_V1_STR}/items/",
        headers=a_headers,
        json={"title": "Secret item"},
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

    # User B can't see A's item in their own organization
    r = client.get(f"{settings.API_V1_STR}/items/{item_id}", headers=b_headers)
    assert r.status_code == 403

    # User A can see their own
    r = client.get(f"{settings.API_V1_STR}/items/", headers=a_headers)
    assert r.status_code == 200
    assert len(r.json()["data"]) >= 1
