from app.agents.fix import FixAgent
from app.core.models import (
    Evidence,
    IssueRequest,
    RootCauseAnalysis,
)
from app.llm.interface import LLMClient
from app.tools.patcher import PatchApplier
from app.tools.validation_service import ValidationService
from app.tools.validator import TestRunner


class FakeFixLLM(LLMClient):
    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        assert "Calculation returns incorrect result" in prompt
        assert "calculator.py" in prompt

        return """
        {
            "summary": "Correct the calculation result.",
            "affected_files": ["calculator.py"],
            "patch": "--- a/calculator.py\\n+++ b/calculator.py\\n@@ -1,2 +1,2 @@\\n def calculate():\\n-    return 1\\n+    return 2\\n",
            "reasoning": "The function returns 1 while the expected result is 2."
        }
        """


def test_fix_agent_output_can_be_validated(tmp_path):
    repository = tmp_path / "project"
    repository.mkdir()

    source_file = repository / "calculator.py"

    source_file.write_text(
        "def calculate():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    test_file = repository / "test_calculator.py"

    test_file.write_text(
        "from calculator import calculate\n\n"
        "def test_calculate():\n"
        "    assert calculate() == 2\n",
        encoding="utf-8",
    )

    issue = IssueRequest(
        title="Calculation returns incorrect result",
        description=(
            "The calculator returns 1 but the expected "
            "result is 2."
        ),
        repository_path=str(repository),
    )

    root_cause = RootCauseAnalysis(
        root_cause=(
            "The calculate function returns the wrong value."
        ),
        explanation=(
            "The implementation returns 1 while the test "
            "expects 2."
        ),
        affected_files=["calculator.py"],
        evidence=[
            "calculator.py returns 1.",
            "test_calculator.py expects 2.",
        ],
        confidence=0.96,
    )

    evidence = [
        Evidence(
            source="calculator.py",
            content=(
                "def calculate():\n"
                "    return 1"
            ),
            score=0.95,
            start_line=1,
            end_line=2,
            language="python",
        )
    ]

    fix_agent = FixAgent(
        llm=FakeFixLLM()
    )

    proposed_fix = fix_agent.generate_fix(
        issue=issue,
        root_cause=root_cause,
        evidence=evidence,
    )

    assert proposed_fix.affected_files == [
        "calculator.py"
    ]
    assert proposed_fix.patch

    validation_service = ValidationService(
        patcher=PatchApplier(),
        test_runner=TestRunner(),
    )

    result = validation_service.validate(
        repository,
        proposed_fix,
        command=["pytest", "-q"],
    )

    assert result.passed is True
    assert result.tests_run == 1
    assert result.tests_passed == 1
    assert result.tests_failed == 0

    # Original repository must remain unchanged.
    assert source_file.read_text(
        encoding="utf-8"
    ) == (
        "def calculate():\n"
        "    return 1\n"
    )