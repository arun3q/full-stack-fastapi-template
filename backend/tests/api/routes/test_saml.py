from fastapi.testclient import TestClient

from app.core.config import settings


def test_saml_status_unconfigured(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/auth/saml/status")
    assert r.status_code == 200
    assert r.json() == {"message": "not-configured"}


def test_saml_metadata_unconfigured_503(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/auth/saml/metadata")
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]
