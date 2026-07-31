from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from app.core.config import settings


def test_metrics_open_when_no_token(client: TestClient) -> None:
    with patch.object(settings, "METRICS_TOKEN", None):
        r = client.get("/metrics")
        assert r.status_code == 200


def test_metrics_requires_token(client: TestClient) -> None:
    with patch.object(settings, "METRICS_TOKEN", "secret"):
        r = client.get("/metrics")
        assert r.status_code == 401
        r = client.get("/metrics", headers={"Authorization": "Bearer secret"})
        assert r.status_code == 200


def test_compose_prod_is_valid_yaml() -> None:
    import pathlib

    path = pathlib.Path(__file__).resolve().parents[4] / "compose.prod.yml"
    data = yaml.safe_load(path.read_text())
    services = data.get("services", {})
    assert "pgbouncer" in services
    assert "prometheus" in services
    assert "worker" in services
