from fastapi.testclient import TestClient

from app.api.main import app
from app.repair.repos import list_authorized_repositories


def test_health_and_cors_for_vite_origin():
    client = TestClient(app)
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    preflight = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code in {200, 204}
    assert preflight.headers.get("access-control-allow-origin") == "http://localhost:5173"

    ipv4 = client.get("/api/v1/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert ipv4.status_code == 200
    assert ipv4.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_repair_repositories_lists_six_demos():
    items = list_authorized_repositories()
    names = {item["name"] for item in items}
    expected = {
        "01_python_import_error",
        "02_fastapi_backend_failure",
        "03_js_runtime_bug",
        "04_database_integration_bug",
        "05_config_env_bug",
        "06_regression_test_failure",
        "sample_project",
    }
    assert expected.issubset(names)
    assert "app" not in names
    assert "docs" not in names


def test_repair_repositories_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/repair/repositories")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert any(item["name"] == "01_python_import_error" for item in body["items"])
