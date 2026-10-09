
import json

import pytest

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
    WorkflowError,
)
from app.core.report import (
    FinalDebuggingReport,
    ReportBuilder,
)
from app.core.workflow import DebuggingState


def build_completed_state(
    *,
    validation_passed: bool = True,
) -> DebuggingState:
    issue = IssueRequest(
        title="Calculation is incorrect",
        description="The calculator returns 1 instead of 2.",
        repository_path="data/sample_project",
    )

    analysis = IssueAnalysis(
        issue_type=IssueType.BUG,
        priority=IssuePriority.HIGH,
        summary="Calculator returns an incorrect result.",
        affected_components=["calculator"],
        search_queries=["calculator incorrect result"],
    )

    evidence = [
        Evidence(
            source="calculator.py",
            content="return 1",
            score=0.95,
            start_line=2,
            end_line=2,
            language="python",
        )
    ]

    root_cause = RootCauseAnalysis(
        root_cause="The calculator returns the wrong value.",
        explanation="The function returns 1 instead of 2.",
        affected_files=["calculator.py"],
        evidence=["calculator.py returns 1."],
        confidence=0.96,
    )

    proposed_fix = ProposedFix(
        summary="Return the correct value.",
        affected_files=["calculator.py"],
        patch="--- a/calculator.py\n+++ b/calculator.py",
        reasoning="The function should return 2.",
    )

    validation = ValidationResult(
        passed=validation_passed,
        tests_run=1,
        tests_passed=1 if validation_passed else 0,
        tests_failed=0 if validation_passed else 1,
        output="1 passed" if validation_passed else "1 failed",
        errors=[] if validation_passed else ["Test failed."],
    )

    return DebuggingState(
        issue=issue,
        analysis=analysis,
        evidence=evidence,
        root_cause=root_cause,
        proposed_fix=proposed_fix,
        validation=validation,
        validation_attempts=1,
    )


def test_report_builder_creates_validated_report():
    state = build_completed_state()

    report = ReportBuilder().build(state)

    assert isinstance(report, FinalDebuggingReport)

    assert report.issue == state.issue
    assert report.analysis == state.analysis
    assert report.root_cause == state.root_cause
    assert report.evidence == state.evidence
    assert report.proposed_fix == state.proposed_fix
    assert report.validation == state.validation

    assert report.status == "validated"
    assert report.run_id == state.run_id
    assert report.created_at == state.created_at
    assert report.validation_attempts == state.validation_attempts
    assert report.stage_traces == state.stage_traces
    assert report.errors == state.errors


def test_report_builder_creates_failed_report():
    state = build_completed_state(
        validation_passed=False
    )

    report = ReportBuilder().build(state)

    assert report.status == "failed"
    assert (
        report.message
        == "The proposed fix could not be successfully validated."
    )


def test_report_builder_requires_analysis():
    state = DebuggingState(
        issue=IssueRequest(
            title="Test issue",
            description="Something is wrong.",
            repository_path="data/sample_project",
        )
    )

    with pytest.raises(
        ValueError,
        match="without issue analysis",
    ):
        ReportBuilder().build(state)


def test_report_includes_stage_traces_and_errors():
    state = build_completed_state()

    trace = StageTrace(
        stage="analyze",
        status="completed",
        duration_ms=12.5,
    )

    error = WorkflowError(
        stage="retrieve",
        error_type="RuntimeError",
        message="A simulated retrieval warning.",
    )

    state.stage_traces.append(trace)
    state.errors.append(error)

    report = ReportBuilder().build(state)

    assert report.stage_traces == [trace]
    assert report.errors == [error]
    assert report.stage_traces[0].duration_ms == 12.5
    assert report.errors[0].error_type == "RuntimeError"


def test_report_serializes_to_json():
    state = build_completed_state()
    report = ReportBuilder().build(state)

    serialized = report.model_dump_json()
    payload = json.loads(serialized)

    assert payload["run_id"] == state.run_id
    assert payload["status"] == "validated"
    assert payload["validation_attempts"] == 1
    assert payload["issue"]["title"] == state.issue.title
    assert payload["validation"]["passed"] is True
    assert payload["stage_traces"] == []
    assert payload["errors"] == []


def test_report_builder_requires_root_cause():
    state = build_completed_state()
    state.root_cause = None

    with pytest.raises(
        ValueError,
        match="without root-cause analysis",
    ):
        ReportBuilder().build(state)


def test_report_builder_requires_proposed_fix():
    state = build_completed_state()
    state.proposed_fix = None

    with pytest.raises(
        ValueError,
        match="without a proposed fix",
    ):
        ReportBuilder().build(state)


def test_report_builder_requires_validation():
    state = build_completed_state()
    state.validation = None

    with pytest.raises(
        ValueError,
        match="without validation results",
    ):
        ReportBuilder().build(state)