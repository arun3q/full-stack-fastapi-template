from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.models import UserCreate
from app.utils import generate_verify_email_token
from tests.utils.utils import random_email, random_lower_string


async def test_verify_email_flow(client: TestClient, db: AsyncSession) -> None:
    email = random_email()
    password = random_lower_string()
    user = await crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
    assert user.is_verified is False

    token = generate_verify_email_token(email=email)
    r = client.post(
        f"{settings.API_V1_STR}/users/verify-email",
        json={"token": token},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Email verified successfully"


async def test_verify_email_invalid_token(client: TestClient) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/users/verify-email",
        json={"token": "not-a-valid-token"},
    )
    assert r.status_code == 400


async def test_verify_email_already_verified(
    client: TestClient, db: AsyncSession
) -> None:
    email = random_email()
    password = random_lower_string()
    await crud.create_user(
        session=db,
        user_create=UserCreate(email=email, password=password, is_verified=True),
    )
    token = generate_verify_email_token(email=email)
    r = client.post(
        f"{settings.API_V1_STR}/users/verify-email",
        json={"token": token},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Email already verified"


async def test_resend_verification_email_unknown_user(
    client: TestClient,
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/users/verify-email/resend",
        json={"email": "ghost@example.com"},
    )
    # Always return the same message to prevent email enumeration
    assert r.status_code == 200
