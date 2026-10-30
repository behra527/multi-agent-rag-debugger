import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app

client = TestClient(app, raise_server_exceptions=False)


def test_get_user_returns_email():
    response = client.get("/users/1")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Ada"
    assert body["email"] == "ada@example.test"
