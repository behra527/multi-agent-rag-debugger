import pytest

from app.core.models import IssueAnalysis
from app.llm.structured import parse_json_response


def test_parse_valid_issue_analysis():
    response = """
    {
        "issue_type": "bug",
        "priority": "high",
        "summary": "Login validation is failing.",
        "affected_components": ["authentication"],
        "search_queries": ["login validation", "authentication"]
    }
    """

    result = parse_json_response(response, IssueAnalysis)

    assert isinstance(result, IssueAnalysis)
    assert result.priority.value == "high"
    assert "authentication" in result.affected_components


def test_parse_invalid_json():
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_json_response(
            "This is not JSON.",
            IssueAnalysis,
        )


def test_parse_invalid_schema():
    response = """
    {
        "issue_type": "invalid_type",
        "priority": "high",
        "summary": "Login validation is failing."
    }
    """

    with pytest.raises(
        ValueError,
        match="does not match IssueAnalysis",
    ):
        parse_json_response(response, IssueAnalysis)