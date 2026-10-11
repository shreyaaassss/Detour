from fastapi.testclient import TestClient

from detour.api import create_app


def test_health():
    body = TestClient(create_app(None)).get("/health").json()
    assert body["status"] == "ok"
