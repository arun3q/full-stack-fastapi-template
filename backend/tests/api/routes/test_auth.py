from fastapi.testclient import TestClient

from app.core.config import settings


def test_auth_providers(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/auth/providers")
    assert r.status_code == 200
    # No credentials configured in the test environment
    assert r.json() == {"providers": []}


def test_auth_login_not_configured(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/auth/google")
    assert r.status_code == 404
    assert "not configured" in r.json()["detail"]
