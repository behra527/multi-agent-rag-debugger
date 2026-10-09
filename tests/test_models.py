
import pytest
from pydantic import ValidationError

from app.core.models import (
    Evidence,
    IssueAnalysis,
    IssuePriority,
    IssueRequest,
    IssueType,
)


def test_issue_request_accepts_valid_data():
    issue = IssueRequest(
        title="Login fails",
        description="Users receive a 500 error during login.",
        repository_path="data/sample_project",
    )

    assert issue.title == "Login fails"
    assert issue.repository_path == "data/sample_project"


def test_issue_request_rejects_empty_title():
    with pytest.raises(ValidationError):
        IssueRequest(
            title="",
            description="Something is broken.",
            repository_path="data/sample_project",
        )


def test_issue_analysis_uses_typed_enums():
    analysis = IssueAnalysis(
        issue_type=IssueType.BUG,
        priority=IssuePriority.HIGH,
        summary="Login validation is failing.",
    )

    assert analysis.issue_type == IssueType.BUG
    assert analysis.priority == IssuePriority.HIGH


def test_evidence_accepts_valid_data():
    evidence = Evidence(
        source="login.py",
        content="def login():",
        score=0.82,
        start_line=1,
        end_line=3,
        language="python",
    )

    assert evidence.source == "login.py"
    assert evidence.score == 0.82
    assert evidence.start_line == 1
    assert evidence.end_line == 3

