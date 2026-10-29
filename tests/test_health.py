from fastapi.testclient import TestClient

from iam_proxy_demo.app import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_rejects_post() -> None:
    response = client.post("/health")
    assert response.status_code == 405
