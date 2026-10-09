
from app.agents.fix import FixAgent
from app.core.models import (
    Evidence,
    IssueRequest,
    ProposedFix,
    RootCauseAnalysis,
)
from app.llm.interface import LLMClient


class FakeLLM(LLMClient):
    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        assert "Login authentication error" in prompt
        assert "login.py" in prompt
        assert "credentials" in prompt
        assert system_prompt is not None

        return """
        {
            "summary": "Validate the supplied credentials before returning a successful login result.",
            "affected_files": ["login.py"],
            "patch": "--- a/login.py\\n+++ b/login.py\\n@@ -1,4 +1,4 @@\\n def login(username, password):\\n-    if username and password:\\n+    if username == \\"admin\\" and password == \\"correct-password\\":\\n         return True",
            "reasoning": "The current implementation only checks whether both values are present instead of validating the credentials."
        }
        """


def test_fix_agent_returns_proposed_fix():
    llm = FakeLLM()
    agent = FixAgent(llm)

    issue = IssueRequest(
        title="Login authentication error",
        description=(
            "Users report that login authentication "
            "is not working correctly."
        ),
        repository_path="data/sample_project",
    )

    root_cause = RootCauseAnalysis(
        root_cause=(
            "The login function only checks whether "
            "username and password values are present."
        ),
        explanation=(
            "The function does not validate whether "
            "the supplied credentials are correct."
        ),
        affected_files=["login.py"],
        evidence=[
            "login.py contains the login function.",
            "The function returns True when username and "
            "password are non-empty.",
        ],
        confidence=0.88,
    )

    evidence = [
        Evidence(
            source="login.py",
            content=(
                "def login(username, password):\n"
                "    if username and password:\n"
                "        return True"
            ),
            score=0.91,
            start_line=1,
            end_line=3,
            language="python",
        )
    ]

    result = agent.generate_fix(
        issue=issue,
        root_cause=root_cause,
        evidence=evidence,
    )

    assert isinstance(result, ProposedFix)
    assert result.summary
    assert result.affected_files == ["login.py"]
    assert result.patch.startswith("--- a/login.py")
    assert "credentials" in result.reasoning

