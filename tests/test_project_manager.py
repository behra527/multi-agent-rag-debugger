from app.agents.fix import FixAgent
from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.root_cause import RootCauseAgent
from app.core.debugging_workflow import DebuggingWorkflow
from app.core.models import (
    IssueAnalysis,
    IssuePriority,
    IssueRequest,
    IssueType,
    ProposedFix,
    RootCauseAnalysis,
    ValidationResult,
)
from app.core.project_manager import ProjectManager
from app.core.supervisor import Supervisor
from app.core.workflow import DebuggingState
from app.rag.chunker import RepositoryChunker
from app.rag.embeddings import EmbeddingProvider
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.indexer import RepositoryIndexer
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.loader import RepositoryLoader
from app.rag.retriever import RepositoryRetriever
from app.rag.scanner import RepositoryScanner
from app.rag.vector_store import VectorStore
from app.tools.patcher import PatchApplier
from app.tools.validation_service import ValidationService
from app.tools.validator import TestRunner


class FakeWorkflow:
    """Fake workflow used to test ProjectManager independently."""

    def run(
        self,
        state: DebuggingState,
        *,
        top_k: int = 5,
        validation_command: list[str] | None = None,
        max_steps: int = 10,
    ) -> DebuggingState:
        state.analysis = IssueAnalysis(
            issue_type=IssueType.BUG,
            priority=IssuePriority.HIGH,
            summary="Calculator returns the wrong result.",
            affected_components=["calculator"],
            search_queries=["calculator return"],
        )

        state.root_cause = RootCauseAnalysis(
            root_cause="Calculator returns 1 instead of 2.",
            explanation="The calculate function contains the wrong value.",
            affected_files=["calculator.py"],
            evidence=["calculator.py returns 1."],
            confidence=0.96,
        )

        state.proposed_fix = ProposedFix(
            summary="Change calculator result from 1 to 2.",
            affected_files=["calculator.py"],
            patch=(
                "--- a/calculator.py\n"
                "+++ b/calculator.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def calculate():\n"
                "-    return 1\n"
                "+    return 2\n"
            ),
            reasoning="The expected result is 2.",
        )

        state.validation = ValidationResult(
            passed=True,
            tests_run=1,
            tests_passed=1,
            tests_failed=0,
            output="1 passed",
            errors=[],
        )

        state.validation_attempts = 1

        return state


class FakeProjectManagerLLM:
    """Deterministic LLM used for ProjectManager integration testing."""

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:

        if "software issue analysis agent" in system_prompt:
            return """
            {
                "issue_type": "bug",
                "priority": "high",
                "summary": "The calculator returns an incorrect result.",
                "affected_components": ["calculator"],
                "search_queries": ["calculator return incorrect result"]
            }
            """

        if "root-cause analysis agent" in system_prompt:
            return """
            {
                "root_cause": "The calculate function returns 1 instead of 2.",
                "explanation": "The implementation returns the wrong value.",
                "affected_files": ["calculator.py"],
                "evidence": [
                    "calculator.py returns 1."
                ],
                "confidence": 0.96
            }
            """

        if "fix generation agent" in system_prompt:
            return """
            {
                "summary": "Correct the calculator result.",
                "affected_files": ["calculator.py"],
                "patch": "--- a/calculator.py\\n+++ b/calculator.py\\n@@ -1,2 +1,2 @@\\n def calculate():\\n-    return 1\\n+    return 2\\n",
                "reasoning": "The function must return 2."
            }
            """

        raise AssertionError(
            "Unexpected system prompt."
        )


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for ProjectManager tests."""

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [
            [1.0, 0.0]
            for _ in texts
        ]


def build_real_workflow(llm) -> DebuggingWorkflow:
    """Build the real debugging workflow with deterministic dependencies."""

    issue_analyzer = IssueAnalyzer(
        llm=llm
    )

    root_cause_agent = RootCauseAgent(
        llm=llm
    )

    fix_agent = FixAgent(
        llm=llm
    )

    embedding_provider = FakeEmbeddingProvider()

    vector_store = VectorStore(
        dimension=2
    )

    indexer = RepositoryIndexer(
        scanner=RepositoryScanner(),
        loader=RepositoryLoader(),
        chunker=RepositoryChunker(
            chunk_size=20
        ),
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    keyword_retriever = KeywordRetriever()

    vector_retriever = RepositoryRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    retriever = HybridRetriever(
        keyword_retriever=keyword_retriever,
        vector_retriever=vector_retriever,
    )

    validation_service = ValidationService(
        patcher=PatchApplier(),
        test_runner=TestRunner(),
    )

    return DebuggingWorkflow(
        issue_analyzer=issue_analyzer,
        indexer=indexer,
        retriever=retriever,
        root_cause_agent=root_cause_agent,
        fix_agent=fix_agent,
        validation_service=validation_service,
        supervisor=Supervisor(),
    )


def test_project_manager_creates_report_from_workflow():
    issue = IssueRequest(
        title="Calculator bug",
        description="The calculator returns the wrong result.",
        repository_path="fake-repository",
    )

    manager = ProjectManager(
        workflow=FakeWorkflow()
    )

    result = manager.handle_issue(
        issue
    )

    assert result.issue == issue

    assert result.analysis.issue_type == IssueType.BUG
    assert result.analysis.priority == IssuePriority.HIGH

    assert result.root_cause.root_cause == (
        "Calculator returns 1 instead of 2."
    )

    assert result.proposed_fix.affected_files == [
        "calculator.py"
    ]

    assert result.validation.passed is True
    assert result.validation.tests_passed == 1

    assert result.status == "validated"

    assert result.message == (
        "The proposed fix was applied in an isolated "
        "workspace and passed validation."
    )


def test_project_manager_runs_real_debugging_workflow(
    tmp_path,
):
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

    llm = FakeProjectManagerLLM()

    workflow = build_real_workflow(
        llm
    )

    manager = ProjectManager(
        workflow=workflow
    )

    result = manager.handle_issue(
        issue,
        top_k=3,
        validation_command=["pytest", "-q"],
    )

    assert result.issue == issue

    assert result.analysis.issue_type == IssueType.BUG
    assert result.analysis.priority == IssuePriority.HIGH

    assert result.root_cause is not None
    assert result.root_cause.affected_files == [
        "calculator.py"
    ]

    assert result.evidence

    assert result.proposed_fix is not None
    assert result.proposed_fix.patch

    assert result.validation.passed is True
    assert result.validation.tests_run == 1
    assert result.validation.tests_passed == 1
    assert result.validation.tests_failed == 0

    assert result.status == "validated"

    assert result.message == (
        "The proposed fix was applied in an isolated "
        "workspace and passed validation."
    )

    # The original repository must remain unchanged.
    assert source_file.read_text(
        encoding="utf-8"
    ) == (
        "def calculate():\n"
        "    return 1\n"
    )