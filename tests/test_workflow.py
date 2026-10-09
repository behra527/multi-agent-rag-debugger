from app.core.models import IssueRequest
from app.core.workflow import DebuggingState


def test_debugging_state_starts_with_issue_only():
    issue = IssueRequest(
        title="Login fails",
        description="Users cannot log in.",
        repository_path="data/sample_project",
    )

    state = DebuggingState(
        issue=issue
    )

    assert state.issue == issue
    assert state.analysis is None
    assert state.evidence == []
    assert state.root_cause is None
    assert state.proposed_fix is None
    assert state.validation is None