import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_ai_status_endpoint_exists(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "disabled")

    response = client.get("/api/ai/status")

    assert response.status_code == 200

    data = response.json()

    assert data["provider"] == "disabled"
    assert data["available"] is False
