import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.db.database import Base, get_db
from app.db.models import DebuggingRunRecord, ProposedFixRecord, ValidationRecord


@pytest.fixture
def git_api_client():
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
        yield client, TestingSessionLocal
    app.dependency_overrides.clear()


def init_test_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Dev Tester"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "dev@test.local"], cwd=path, capture_output=True, check=True)
    (path / "file.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.py"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=path, capture_output=True, check=True)


def test_api_git_status_and_commits(git_api_client, tmp_path):
    client, _ = git_api_client
    repo = tmp_path / "git_api_repo"
    repo.mkdir()
    init_test_git_repo(repo)

    # 1. Get status
    res = client.get(f"/api/v1/git/status?repository_path={repo}")
    assert res.status_code == 200
    data = res.json()
    assert data["is_git"] is True
    assert data["current_branch"] in {"main", "master"}
    assert data["commit_sha"] is not None
    assert data["is_clean"] is True
    assert data["detected_framework"] == "Python"

    # 2. Get commits
    c_res = client.get(f"/api/v1/git/commits?repository_path={repo}&limit=5")
    assert c_res.status_code == 200
    commits = c_res.json()
    assert len(commits) == 1
    assert commits[0]["message"] == "Initial commit"


def test_api_git_branch(git_api_client, tmp_path):
    client, _ = git_api_client
    repo = tmp_path / "git_branch_repo"
    repo.mkdir()
    init_test_git_repo(repo)

    res = client.post(
        "/api/v1/git/branch",
        json={"repository_path": str(repo), "branch_name": "fix/test-patch"},
    )
    assert res.status_code == 200
    assert res.json()["created"] is True
    assert res.json()["branch"] == "fix/test-patch"


def test_api_git_commit_requires_approval(git_api_client, tmp_path):
    client, SessionLocal = git_api_client
    repo = tmp_path / "git_commit_repo"
    repo.mkdir()
    init_test_git_repo(repo)

    # Seed an unapproved run in DB
    db = SessionLocal()
    run = DebuggingRunRecord(
        id="run-12345",
        status="completed",
        title="Bug in file.py",
        description="Fix hello return value",
        repository_path=str(repo),
        approval_status="pending",  # NOT approved
    )
    run.proposed_fix = ProposedFixRecord(
        run_id="run-12345",
        summary="Fix return value",
        affected_files_json='["file.py"]',
        patch="diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n@@ -1,2 +1,2 @@\n def hello():\n-    return 'world'\n+    return 'universe'\n",
        reasoning="Test fix",
    )
    run.validation = ValidationRecord(
        run_id="run-12345",
        passed=True,
    )
    db.add(run)
    db.commit()
    db.close()

    # Attempt commit when unapproved -> 403 Forbidden
    commit_res = client.post(
        "/api/v1/git/commit",
        json={
            "repository_path": str(repo),
            "run_id": "run-12345",
            "branch_name": "fix/universe",
        },
    )
    assert commit_res.status_code == 403
    assert "the patch has not been approved" in commit_res.json()["detail"]

    # Now approve the run
    approve_res = client.post(
        "/api/v1/debugging-runs/run-12345/approval",
        json={"status": "approved", "reviewer": "team_lead"},
    )
    assert approve_res.status_code == 200

    # Commit again -> 200 OK
    commit_res2 = client.post(
        "/api/v1/git/commit",
        json={
            "repository_path": str(repo),
            "run_id": "run-12345",
            "branch_name": "fix/universe",
            "commit_message": "fix(file): update hello greeting",
        },
    )
    assert commit_res2.status_code == 200
    assert commit_res2.json()["commit_sha"] is not None
    assert "file.py" in commit_res2.json()["modified_files"]
