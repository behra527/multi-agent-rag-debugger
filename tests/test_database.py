from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.models import (
    Evidence,
    IssueAnalysis,
    IssuePriority,
    IssueRequest,
    IssueType,
    ProposedFix,
    RootCauseAnalysis,
    StageTrace,
    ValidationResult,
)
from app.core.report import FinalDebuggingReport
from app.db.database import Base
from app.db.repository_service import PersistenceService


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True)
    session = session_factory()
    yield session
    session.close()


def test_persistence_service_save_and_retrieve_report(test_db):
    report = FinalDebuggingReport(
        run_id="run-test-123",
        created_at=datetime.now(timezone.utc),
        issue=IssueRequest(
            title="Login crash",
            description="Null pointer in login handler",
            repository_path="d:/dummy/repo",
        ),
        analysis=IssueAnalysis(
            issue_type=IssueType.BUG,
            priority=IssuePriority.HIGH,
            summary="Login handler fails",
            affected_components=["auth"],
            search_queries=["def login"],
        ),
        root_cause=RootCauseAnalysis(
            root_cause="Null user object",
            explanation="User is not verified before lookup",
            affected_files=["auth.py"],
            evidence=["None check missing"],
            confidence=0.9,
        ),
        evidence=[
            Evidence(
                source="auth.py",
                content="user = get_user()",
                score=0.92,
                start_line=10,
                end_line=15,
                language="python",
            )
        ],
        proposed_fix=ProposedFix(
            summary="Add null guard",
            affected_files=["auth.py"],
            patch="diff --git a/auth.py b/auth.py\n+if not user: return False",
            reasoning="Prevents crash when user is None",
        ),
        validation=ValidationResult(
            passed=True,
            tests_run=5,
            tests_passed=5,
            tests_failed=0,
            output="5 passed",
            errors=[],
        ),
        validation_attempts=1,
        stage_traces=[
            StageTrace(
                stage="analyze",
                status="completed",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                duration_ms=45.2,
            )
        ],
        errors=[],
        status="completed",
        message="Debugging workflow completed successfully.",
    )

    # Save report
    record = PersistenceService.save_report(report, test_db)
    assert record.id == "run-test-123"
    assert record.status == "completed"

    # Query back
    fetched = PersistenceService.get_run("run-test-123", test_db)
    assert fetched is not None
    assert fetched.title == "Login crash"
    assert fetched.analysis.summary == "Login handler fails"
    assert fetched.root_cause.confidence == 0.9
    assert len(fetched.evidence_items) == 1
    assert fetched.validation.passed is True

    # Record human approval
    approval = PersistenceService.record_approval(
        "run-test-123",
        status="approved",
        reviewer="lead_engineer",
        comment="Looks great!",
        db=test_db,
    )
    assert approval.status == "approved"
    assert fetched.approval_status == "approved"

    # Verify metrics
    metrics = PersistenceService.get_metrics(test_db)
    assert metrics["total_runs"] == 1
    assert metrics["completed_runs"] == 1
    assert metrics["approved_fixes"] == 1
    assert metrics["success_rate"] == 100.0
