from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health_endpoint_exists():
    response = client.get("/api/health")
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    # Using the client as a context manager ensures FastAPI
    # startup/lifespan events run, which is where app.state.neo4j
    # is likely initialized.
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint_exists(client):
    response = client.get("/api/health")

    # If Neo4j is not available in the test environment,
    # the endpoint may return 503 instead of 200.
    assert response.status_code in [200, 503]

    # If Neo4j is not running in the test environment,
    # the endpoint may return 503 instead of 200.
    assert response.status_code in [200, 503]
