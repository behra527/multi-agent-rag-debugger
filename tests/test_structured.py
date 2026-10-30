
import pytest

from app.core.models import IssueAnalysis
from app.llm.structured import parse_json_response


VALID_ISSUE_JSON = """
{
    "issue_type": "bug",
    "priority": "high",
    "summary": "Login validation is failing.",
    "affected_components": ["authentication"],
    "search_queries": ["login validation", "authentication"]
}
"""


def test_parse_valid_issue_analysis():
    result = parse_json_response(
        VALID_ISSUE_JSON,
        IssueAnalysis,
    )

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


def test_parse_json_markdown_code_fence():
    response = f"```json\n{VALID_ISSUE_JSON}\n```"

    result = parse_json_response(response, IssueAnalysis)

    assert isinstance(result, IssueAnalysis)
    assert result.priority.value == "high"


def test_parse_json_with_surrounding_text():
    response = (
        "Here is the analysis:\n"
        f"{VALID_ISSUE_JSON}\n"
        "End of response."
    )

    result = parse_json_response(response, IssueAnalysis)

    assert isinstance(result, IssueAnalysis)
    assert result.summary == "Login validation is failing."


def test_parse_empty_response():
    with pytest.raises(
        ValueError,
        match="empty response",
    ):
        parse_json_response("", IssueAnalysis)
