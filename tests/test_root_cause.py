
from app.agents.root_cause import RootCauseAgent
from app.core.models import (
    Evidence,
    IssueAnalysis,
    IssuePriority,
    IssueRequest,
    IssueType,
)
from app.llm.interface import LLMClient


class FakeLLM(LLMClient):
    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        assert "login authentication" in prompt
        assert "login.py" in prompt
        assert system_prompt is not None

        return """
        {
            "root_cause": "The login function does not validate credentials correctly.",
            "explanation": "The retrieved login implementation only checks whether username and password values exist.",
            "affected_files": ["login.py"],
            "evidence": [
                "login.py contains the login function.",
                "The function only checks whether username and password are present."
            ],
            "confidence": 0.91
        }
        """


def test_root_cause_agent_returns_structured_analysis():
    llm = FakeLLM()
    agent = RootCauseAgent(llm)

    issue = IssueRequest(
        title="Login authentication error",
        description="Users report that login authentication is not working correctly.",
        repository_path="data/sample_project",
    )

    analysis = IssueAnalysis(
        issue_type=IssueType.ERROR,
        priority=IssuePriority.HIGH,
        summary="Login authentication is failing.",
        affected_components=["login"],
        search_queries=["login authentication"],
    )

    evidence = [
        Evidence(
            source="login.py",
            content="def login(username, password):\n    if username and password:\n        return True",
            score=0.91,
            start_line=1,
            end_line=3,
            language="python",
        )
    ]

    result = agent.analyze(
        issue=issue,
        analysis=analysis,
        evidence=evidence,
    )

    assert result.root_cause
    assert result.explanation
    assert result.affected_files == ["login.py"]
    assert len(result.evidence) == 2
    assert result.confidence == 0.91

