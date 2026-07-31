from fastapi.testclient import TestClient

from app.core.config import settings


def test_ai_health_disabled(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/ai/health",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    content = r.json()
    assert content["configured"] is False


def test_ai_chat_not_configured(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/ai/chat",
        headers=superuser_token_headers,
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert r.status_code == 503
