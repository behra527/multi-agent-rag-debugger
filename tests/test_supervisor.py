from app.core.models import (
    IssueAnalysis,
    IssuePriority,
    IssueRequest,
    IssueType,
    ProposedFix,
    RootCauseAnalysis,
    ValidationResult,
)
from app.core.supervisor import Supervisor, WorkflowStage
from app.core.workflow import DebuggingState


def create_state() -> DebuggingState:
    """Create a valid base debugging state for supervisor tests."""

    issue = IssueRequest(
        title="Login fails",
        description="Users cannot log in.",
        repository_path="data/sample_project",
    )

    return DebuggingState(issue=issue)


def create_analysis() -> IssueAnalysis:
    return IssueAnalysis(
        issue_type=IssueType.BUG,
        priority=IssuePriority.HIGH,
        summary="Login functionality is failing.",
        affected_components=["login"],
        search_queries=["login authentication"],
    )


def create_root_cause() -> RootCauseAnalysis:
    return RootCauseAnalysis(
        root_cause="Incorrect login condition.",
        explanation="The login condition does not handle the valid case.",
        affected_files=["login.py"],
        evidence=["login.py contains the incorrect condition."],
        confidence=0.9,
    )


def create_fix() -> ProposedFix:
    return ProposedFix(
        summary="Correct the login condition.",
        affected_files=["login.py"],
        patch="valid patch",
        reasoning="The condition must be corrected.",
    )


def create_validation(
    passed: bool,
) -> ValidationResult:
    return ValidationResult(
        passed=passed,
        tests_run=1,
        tests_passed=1 if passed else 0,
        tests_failed=0 if passed else 1,
    )


def test_supervisor_starts_with_analysis():
    supervisor = Supervisor()
    state = create_state()

    assert (
        supervisor.decide(state)
        == WorkflowStage.ANALYZE
    )


def test_supervisor_moves_to_retrieval_after_analysis():
    supervisor = Supervisor()
    state = create_state()

    state.analysis = create_analysis()

    assert (
        supervisor.decide(state)
        == WorkflowStage.RETRIEVE
    )


def test_supervisor_moves_to_root_cause_after_evidence():
    supervisor = Supervisor()
    state = create_state()

    state.analysis = create_analysis()

    from app.core.models import Evidence

    state.evidence = [
        Evidence(
            source="login.py",
            content="def login():",
            score=0.9,
            start_line=1,
            end_line=1,
            language="python",
        )
    ]

    assert (
        supervisor.decide(state)
        == WorkflowStage.ROOT_CAUSE
    )


def test_supervisor_moves_to_fix_after_root_cause():
    supervisor = Supervisor()
    state = create_state()

    state.analysis = create_analysis()
    state.evidence = ["evidence"]  # type: ignore[list-item]
    state.root_cause = create_root_cause()

    assert (
        supervisor.decide(state)
        == WorkflowStage.GENERATE_FIX
    )


def test_supervisor_moves_to_validation_after_fix():
    supervisor = Supervisor()
    state = create_state()

    state.analysis = create_analysis()
    state.evidence = ["evidence"]  # type: ignore[list-item]
    state.root_cause = create_root_cause()
    state.proposed_fix = create_fix()

    assert (
        supervisor.decide(state)
        == WorkflowStage.VALIDATE
    )


def test_supervisor_completes_after_successful_validation():
    supervisor = Supervisor()
    state = create_state()

    state.analysis = create_analysis()
    state.evidence = ["evidence"]  # type: ignore[list-item]
    state.root_cause = create_root_cause()
    state.proposed_fix = create_fix()
    state.validation = create_validation(True)
    state.validation_attempts = 1

    assert (
        supervisor.decide(state)
        == WorkflowStage.COMPLETE
    )


def test_supervisor_retries_after_failed_validation():
    supervisor = Supervisor()
    state = create_state()

    state.analysis = create_analysis()
    state.evidence = ["evidence"]  # type: ignore[list-item]
    state.root_cause = create_root_cause()
    state.proposed_fix = create_fix()
    state.validation = create_validation(False)
    state.validation_attempts = 1
    state.max_validation_attempts = 2

    stage = supervisor.decide(state)

    assert stage == WorkflowStage.GENERATE_FIX
    assert state.validation is None
    assert state.proposed_fix is None


def test_supervisor_fails_after_max_validation_attempts():
    supervisor = Supervisor()
    state = create_state()

    state.analysis = create_analysis()
    state.evidence = ["evidence"]  # type: ignore[list-item]
    state.root_cause = create_root_cause()
    state.proposed_fix = create_fix()
    state.validation = create_validation(False)
    state.validation_attempts = 2
    state.max_validation_attempts = 2

    assert (
        supervisor.decide(state)
        == WorkflowStage.FAILED
    )