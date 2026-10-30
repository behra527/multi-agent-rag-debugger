"""Regression tests for dynamic repository awareness, cross-repo isolation,
missing file patch rejection, and strict approval rules.

Verifies the critical bugs reported in the dashboard are permanently resolved:
1. Unrelated repositories must never diagnose calculator bugs or target calculator.py.
2. Two different repositories investigated sequentially have zero evidence leakage.
3. Patches targeting non-existent files are rejected before validation execution.
4. Failed validations block approval unless an explicit override reason is provided.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.v1.router import create_project_manager
from app.core.models import IssueRequest, ProposedFix
from app.db.database import Base, get_db
from app.factory import create_project_manager as factory_create_manager
from app.tools.patcher import PatchApplier
from app.tools.validation_service import ValidationService
from app.tools.validator import TestRunner


@pytest.fixture
def isolated_client():
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


def test_regression_unrelated_repo_never_diagnoses_calculator(tmp_path):
    """The system must never diagnose a calculator bug or produce calculator.py

    for an unrelated repository (e.g. system-prompt-lab style repo).
    """
    repo = tmp_path / "system_prompt_lab"
    repo.mkdir()
    (repo / "prompt_evaluator.py").write_text(
        "def evaluate_prompt(prompt: str) -> bool:\n"
        "    if not prompt:\n"
        "        raise ValueError('Empty prompt')\n"
        "    return len(prompt) > 5\n",
        encoding="utf-8",
    )
    (repo / "test_prompt_evaluator.py").write_text(
        "from prompt_evaluator import evaluate_prompt\n"
        "def test_eval():\n"
        "    assert evaluate_prompt('hello world') is True\n",
        encoding="utf-8",
    )

    issue = IssueRequest(
        title="Prompt evaluator fails on empty inputs",
        description="evaluate_prompt raises unexpected ValueError instead of returning False on empty prompt.",
        repository_path=str(repo),
    )

    manager = factory_create_manager(provider="mock")
    report = manager.handle_issue(issue, top_k=3)

    # 1. Affected files must NOT contain calculator.py
    for f in (report.root_cause.affected_files if report.root_cause else []):
        assert "calculator" not in f.lower(), f"Unexpected calculator reference in affected_files: {f}"

    # 2. Patch must NOT target calculator.py
    if report.proposed_fix and report.proposed_fix.patch:
        assert "calculator.py" not in report.proposed_fix.patch, (
            f"Patch targeted calculator.py on unrelated repository! Patch: {report.proposed_fix.patch}"
        )
        assert "prompt_evaluator.py" in report.proposed_fix.patch

    # 3. Evidence must only come from this repository
    assert len(report.evidence) > 0
    for ev in report.evidence:
        assert "calculator" not in ev.source.lower()
        assert "prompt_evaluator" in ev.source.lower()


def test_sequential_repos_have_zero_cross_repo_contamination(tmp_path):
    """Two different repositories debugged sequentially must never leak evidence

    or chunks across sessions.
    """
    # Repo A: Order Service
    repo_a = tmp_path / "order_service"
    repo_a.mkdir()
    (repo_a / "order.py").write_text(
        "def process_order(order_id: int) -> str:\n"
        "    return f'processed-{order_id}'\n",
        encoding="utf-8",
    )

    # Repo B: User Profile Service
    repo_b = tmp_path / "profile_service"
    repo_b.mkdir()
    (repo_b / "profile.py").write_text(
        "def get_user_avatar(user_id: int) -> str:\n"
        "    return f'https://cdn.example.com/avatars/{user_id}.png'\n",
        encoding="utf-8",
    )

    # Run on Repo A
    manager_a = factory_create_manager(provider="mock")
    report_a = manager_a.handle_issue(
        IssueRequest(
            title="Order processing format error",
            description="process_order return string has invalid prefix.",
            repository_path=str(repo_a),
        ),
        top_k=5,
    )
    for ev in report_a.evidence:
        assert "profile.py" not in ev.source
        assert "order.py" in ev.source

    # Run on Repo B
    manager_b = factory_create_manager(provider="mock")
    report_b = manager_b.handle_issue(
        IssueRequest(
            title="Avatar CDN URL malformed",
            description="get_user_avatar returns HTTP instead of HTTPS.",
            repository_path=str(repo_b),
        ),
        top_k=5,
    )

    # Verify Repo B has NO traces of Repo A
    assert len(report_b.evidence) > 0
    for ev in report_b.evidence:
        assert "order.py" not in ev.source, f"Cross-repo contamination: found {ev.source} in repo B evidence!"
        assert "profile.py" in ev.source


def test_missing_patch_file_rejected_before_execution(tmp_path):
    """A patch targeting a file that does not exist in the repository must be

    rejected with a clear error before sandbox execution.
    """
    repo = tmp_path / "my_project"
    repo.mkdir()
    (repo / "index.js").write_text("console.log('hello');\n", encoding="utf-8")

    # This patch maliciously or accidentally targets calculator.py which does not exist
    patch = (
        "diff --git a/calculator.py b/calculator.py\n"
        "--- a/calculator.py\n"
        "+++ b/calculator.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-def calculate(): return 1\n"
        "+def calculate(): return 2\n"
    )

    fix = ProposedFix(
        summary="Bogus fix targeting missing calculator.py",
        affected_files=["calculator.py"],
        patch=patch,
        reasoning="Attempting to fix non-existent file",
    )

    service = ValidationService(
        patcher=PatchApplier(),
        test_runner=TestRunner(),
    )

    result = service.validate(repo, fix)
    assert result.passed is False
    assert len(result.errors) > 0
    assert any("not exist in the target repository" in err for err in result.errors)


def test_approval_blocks_failed_validation_without_override(isolated_client, tmp_path):
    """Submitting approval for a run whose validation failed must return 409

    unless an explicit override reason is provided.
    """
    repo = tmp_path / "failing_repo"
    repo.mkdir()
    # A test that will fail
    (repo / "app.py").write_text("def run(): return False\n", encoding="utf-8")
    (repo / "test_app.py").write_text(
        "from app import run\ndef test_run(): assert run() is True\n",
        encoding="utf-8",
    )

    # Start debugging run
    res = isolated_client.post(
        "/api/v1/debugging-runs",
        json={
            "title": "Failing test",
            "description": "run() fails assertion",
            "repository_path": str(repo),
            "top_k": 2,
            "provider": "mock",
        },
    )
    assert res.status_code == 200
    run_id = res.json()["run_id"]

    # Attempt to approve without override comment -> must be blocked
    approve_res = isolated_client.post(
        f"/api/v1/debugging-runs/{run_id}/approval",
        json={"status": "approved", "reviewer": "developer"},
    )
    assert approve_res.status_code == 409
    assert "Validation failed for this run. Approval is blocked" in approve_res.json()["detail"]

    # Now approve with explicit override reason -> succeeds with audit tracking
    override_res = isolated_client.post(
        f"/api/v1/debugging-runs/{run_id}/approval",
        json={
            "status": "approved",
            "reviewer": "qa_lead",
            "comment": "Override approved: tests will be updated in separate PR",
        },
    )
    assert override_res.status_code == 200
    data = override_res.json()
    assert data["approval_status"] == "approved"
    assert data["validation_override"] is True
    assert data["merge_ready"] is False  # Cannot automatically merge overridden failed checks
    assert "[VALIDATION OVERRIDE]" in data["comment"]
