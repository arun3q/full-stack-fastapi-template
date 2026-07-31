from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.models import OrganizationInvite, UserCreate
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


def _login(client: TestClient, email: str, password: str) -> dict:
    return client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    ).json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_login_returns_refresh_token(
    client: TestClient, db: AsyncSession
) -> None:
    email, password = await _create_user(db)
    data = _login(client, email, password)
    assert data["access_token"]
    assert data["refresh_token"]


async def test_refresh_token_rotation(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    login = _login(client, email, password)
    first_refresh = login["refresh_token"]

    r = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert r.status_code == 200
    rotated = r.json()
    assert rotated["refresh_token"] != first_refresh

    # The old token must no longer work (rotated/revoked)
    r = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert r.status_code == 401


async def test_logout_revokes_session(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    login = _login(client, email, password)
    refresh = login["refresh_token"]

    r = client.post(
        f"{settings.API_V1_STR}/auth/logout", json={"refresh_token": refresh}
    )
    assert r.status_code == 200

    r = client.post(
        f"{settings.API_V1_STR}/auth/refresh", json={"refresh_token": refresh}
    )
    assert r.status_code == 401


async def test_sessions_list_and_revoke(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    login = _login(client, email, password)
    headers = _headers(login["access_token"])

    r = client.get(f"{settings.API_V1_STR}/auth/sessions", headers=headers)
    assert r.status_code == 200
    sessions = r.json()
    assert sessions["count"] >= 1
    session_id = sessions["data"][0]["id"]

    r = client.delete(
        f"{settings.API_V1_STR}/auth/sessions/{session_id}", headers=headers
    )
    assert r.status_code == 200

    r = client.post(
        f"{settings.API_V1_STR}/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )
    assert r.status_code == 401


async def test_totp_flow(client: TestClient, db: AsyncSession) -> None:
    import pyotp

    email, password = await _create_user(db)
    headers = _headers(_login(client, email, password)["access_token"])

    setup = client.post(
        f"{settings.API_V1_STR}/auth/totp/setup",
        headers=headers,
        json={"password": password},
    )
    assert setup.status_code == 200
    secret = setup.json()["secret"]

    code = pyotp.TOTP(secret).now()
    r = client.post(
        f"{settings.API_V1_STR}/auth/totp/enable",
        headers=headers,
        json={"password": password, "code": code},
    )
    assert r.status_code == 200

    # Login now requires the TOTP code
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    )
    assert r.status_code == 400

    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={
            "username": email,
            "password": password,
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )
    assert r.status_code == 200

    # Disable 2FA again
    r = client.post(
        f"{settings.API_V1_STR}/auth/totp/disable",
        headers=headers,
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert r.status_code == 200


async def test_api_key_flow(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    headers = _headers(_login(client, email, password)["access_token"])

    created = client.post(
        f"{settings.API_V1_STR}/api-keys/",
        headers=headers,
        json={"name": "ci-key", "scopes": ["read"]},
    )
    assert created.status_code == 200
    plaintext = created.json()["key"]
    assert plaintext.startswith("sk_")
    key_id = created.json()["id"]

    # Authenticate with the key
    r = client.get(
        f"{settings.API_V1_STR}/api-keys/me", headers={"X-API-Key": plaintext}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "ci-key"

    # Revoke it
    r = client.delete(f"{settings.API_V1_STR}/api-keys/{key_id}", headers=headers)
    assert r.status_code == 200
    r = client.get(
        f"{settings.API_V1_STR}/api-keys/me", headers={"X-API-Key": plaintext}
    )
    assert r.status_code == 401


async def test_invite_notifies_inviter(client: TestClient, db: AsyncSession) -> None:
    owner_email, owner_password = await _create_user(db)
    owner_headers = _headers(
        _login(client, owner_email, owner_password)["access_token"]
    )
    org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=owner_headers,
        json={"name": "Acme"},
    ).json()

    invitee_email, invitee_password = await _create_user(db)
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

    invitee_headers = _headers(
        _login(client, invitee_email, invitee_password)["access_token"]
    )
    r = client.post(
        f"{settings.API_V1_STR}/organizations/invites/{token.token}/accept",
        headers=invitee_headers,
    )
    assert r.status_code == 200

    r = client.get(f"{settings.API_V1_STR}/notifications/", headers=owner_headers)
    assert r.status_code == 200
    assert r.json()["count"] >= 1


async def test_webhook_crud(client: TestClient, db: AsyncSession) -> None:
    email, password = await _create_user(db)
    headers = _headers(_login(client, email, password)["access_token"])

    created = client.post(
        f"{settings.API_V1_STR}/webhooks/",
        headers=headers,
        json={"url": "https://example.com/hook", "events": ["item.created"]},
    )
    assert created.status_code == 200
    webhook_id = created.json()["id"]

    r = client.get(f"{settings.API_V1_STR}/webhooks/", headers=headers)
    assert r.status_code == 200
    assert r.json()["count"] >= 1

    # Test delivery queues a delivery record
    r = client.post(
        f"{settings.API_V1_STR}/webhooks/{webhook_id}/test", headers=headers
    )
    assert r.status_code == 200

    r = client.delete(f"{settings.API_V1_STR}/webhooks/{webhook_id}", headers=headers)
    assert r.status_code == 200


async def test_admin_audit_log(client: TestClient) -> None:
    # A login writes an audit event; the superuser can read the log
    superuser_headers = _headers(
        _login(client, settings.FIRST_SUPERUSER, settings.FIRST_SUPERUSER_PASSWORD)[
            "access_token"
        ]
    )
    r = client.get(f"{settings.API_V1_STR}/admin/audit-log", headers=superuser_headers)
    assert r.status_code == 200
    assert r.json()["count"] >= 1
