from app.agents.issue_analyzer import IssueAnalyzer
from app.core.models import (
    IssueAnalysis,
    IssuePriority,
    IssueRequest,
    IssueType,
)


class FakeLLM:
    """Deterministic fake LLM for unit testing."""

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        return """
        {
            "issue_type": "bug",
            "priority": "high",
            "summary": "Login validation is failing.",
            "affected_components": [
                "authentication",
                "login"
            ],
            "search_queries": [
                "login validation",
                "authentication"
            ]
        }
        """


def test_issue_analyzer_returns_structured_analysis():
    analyzer = IssueAnalyzer(FakeLLM())

    issue = IssueRequest(
        title="Login fails",
        description="Users receive an error when trying to log in.",
        repository_path="data/sample_project",
    )

    result = analyzer.analyze(issue)

    assert isinstance(result, IssueAnalysis)
    assert result.issue_type == IssueType.BUG
    assert result.priority == IssuePriority.HIGH
    assert "authentication" in result.affected_components
    assert len(result.search_queries) == 2