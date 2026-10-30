import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.db.database import Base, get_db


@pytest.fixture(scope="module")
def api_client():
    # Use StaticPool with in-memory SQLite so tables persist across sessions in the test
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, future=True)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_api_v1_health(api_client):
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "multi-agent-rag-debugger"
    assert data["database"] == "connected"


def test_api_v1_metrics(api_client):
    response = api_client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_runs" in data
    assert "success_rate" in data


def test_api_v1_scan_repository(api_client, tmp_path):
    repo = tmp_path / "scan_repo"
    repo.mkdir()
    (repo / "main.py").write_text("print('hello')", encoding="utf-8")

    response = api_client.post(
        "/api/v1/repositories/scan",
        json={"repository_path": str(repo)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["total_files"] == 1
    assert "main.py" in data["files"]


def test_api_v1_settings_roundtrip(api_client):
    get_res = api_client.get("/api/v1/settings")
    assert get_res.status_code == 200
    original_tokens = get_res.json()["llm_max_tokens"]

    update_res = api_client.post(
        "/api/v1/settings",
        json={"llm_max_tokens": 1200, "llm_temperature": 0.3},
    )
    assert update_res.status_code == 200
    assert update_res.json()["llm_max_tokens"] == 1200

    # Reset
    api_client.post("/api/v1/settings", json={"llm_max_tokens": original_tokens})


def test_api_v1_debugging_run_lifecycle(api_client, tmp_path):
    repo = tmp_path / "test_api_calc"
    repo.mkdir()
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    (repo / "test_calculator.py").write_text(
        "from calculator import calculate\ndef test_calculate():\n    assert calculate() == 2\n",
        encoding="utf-8",
    )

    # 1. Start debugging run with Mock provider
    run_payload = {
        "title": "API test issue",
        "description": "calculate returns 1 instead of 2",
        "repository_path": str(repo),
        "top_k": 3,
        "provider": "mock",
    }

    create_res = api_client.post("/api/v1/debugging-runs", json=run_payload)
    assert create_res.status_code == 200
    report = create_res.json()
    run_id = report["run_id"]
    assert report["status"] == "validated"
    assert report["validation"]["passed"] is True

    # 2. List debugging runs
    list_res = api_client.get("/api/v1/debugging-runs")
    assert list_res.status_code == 200
    runs = list_res.json()
    assert len(runs) >= 1
    assert any(r["run_id"] == run_id for r in runs)

    # 3. Get run details
    detail_res = api_client.get(f"/api/v1/debugging-runs/{run_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["title"] == "API test issue"
    assert detail["analysis"]["summary"]
    assert detail["root_cause"]["root_cause"]
    assert detail["proposed_fix"]["patch"]

    # 4. Get evidence
    evidence_res = api_client.get(f"/api/v1/debugging-runs/{run_id}/evidence")
    assert evidence_res.status_code == 200
    evidence_list = evidence_res.json()
    assert len(evidence_list) > 0

    # 5. Get patch
    patch_res = api_client.get(f"/api/v1/debugging-runs/{run_id}/patch")
    assert patch_res.status_code == 200
    assert "diff --git" in patch_res.json()["patch"]

    # 6. Submit human approval
    approval_res = api_client.post(
        f"/api/v1/debugging-runs/{run_id}/approval",
        json={"status": "approved", "reviewer": "qa_lead", "comment": "Verified and passed"},
    )
    assert approval_res.status_code == 200
    assert approval_res.json()["approval_status"] == "approved"
