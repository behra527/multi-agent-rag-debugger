
from app.agents.fix import FixAgent
from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.root_cause import RootCauseAgent
from app.core.debugging_workflow import DebuggingWorkflow
from app.core.models import IssueRequest
from app.core.supervisor import Supervisor
from app.core.workflow import DebuggingState
from app.rag.chunker import RepositoryChunker
from app.rag.embeddings import EmbeddingProvider
from app.rag.evidence import EvidenceRanker
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


class FakeWorkflowLLM:
    """Deterministic LLM used for workflow testing."""

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        system_prompt = system_prompt or ""

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

        raise AssertionError("Unexpected system prompt.")


class RetryWorkflowLLM:
    """Generates a failing fix first and a correct fix second."""

    def __init__(self) -> None:
        self.fix_calls = 0

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        system_prompt = system_prompt or ""

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
            self.fix_calls += 1

            if self.fix_calls == 1:
                return """
                {
                    "summary": "First fix intentionally returns the wrong value.",
                    "affected_files": ["calculator.py"],
                    "patch": "--- a/calculator.py\\n+++ b/calculator.py\\n@@ -1,2 +1,2 @@\\n def calculate():\\n-    return 1\\n+    return 3\\n",
                    "reasoning": "This is the first proposed fix."
                }
                """

            return """
            {
                "summary": "Correct the calculator result.",
                "affected_files": ["calculator.py"],
                "patch": "--- a/calculator.py\\n+++ b/calculator.py\\n@@ -1,2 +1,2 @@\\n def calculate():\\n-    return 1\\n+    return 2\\n",
                "reasoning": "The function must return 2."
            }
            """

        raise AssertionError("Unexpected system prompt.")


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider that tracks embedding calls."""

    def __init__(self) -> None:
        self.call_count = 0
        self.embedded_text_count = 0

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        self.call_count += 1
        self.embedded_text_count += len(texts)

        return [
            [1.0, 0.0]
            for _ in texts
        ]


def build_workflow(
    llm,
    embedding_provider: FakeEmbeddingProvider | None = None,
) -> DebuggingWorkflow:
    """Build a debugging workflow using test dependencies."""

    issue_analyzer = IssueAnalyzer(llm=llm)
    root_cause_agent = RootCauseAgent(llm=llm)
    fix_agent = FixAgent(llm=llm)

    if embedding_provider is None:
        embedding_provider = FakeEmbeddingProvider()

    # This provider is used only when indexing repository documents.
    index_vector_store = VectorStore(dimension=2)

    indexer = RepositoryIndexer(
        scanner=RepositoryScanner(),
        loader=RepositoryLoader(),
        chunker=RepositoryChunker(chunk_size=20),
        embedding_provider=embedding_provider,
        vector_store=index_vector_store,
    )

    keyword_retriever = KeywordRetriever()

    # Query embeddings use a separate provider so index caching
    # can be measured independently from semantic search.
    query_embedding_provider = FakeEmbeddingProvider()

    vector_retriever = RepositoryRetriever(
        embedding_provider=query_embedding_provider,
        vector_store=index_vector_store,
    )

    retriever = HybridRetriever(
        keyword_retriever=keyword_retriever,
        vector_retriever=vector_retriever,
    )

    validation_service = ValidationService(
        patcher=PatchApplier(),
        test_runner=TestRunner(),
    )

    workflow = DebuggingWorkflow(
        issue_analyzer=issue_analyzer,
        indexer=indexer,
        retriever=retriever,
        root_cause_agent=root_cause_agent,
        fix_agent=fix_agent,
        validation_service=validation_service,
        supervisor=Supervisor(),
        evidence_ranker=EvidenceRanker(),
    )

    # Expose providers for integration-test assertions.
    workflow.test_embedding_provider = embedding_provider
    workflow.test_query_embedding_provider = query_embedding_provider

    return workflow


def create_calculator_repository(tmp_path):
    """Create a small repository with a failing calculator test."""

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

    return repository, source_file


def create_issue(repository) -> IssueRequest:
    """Create the calculator issue used by workflow tests."""

    return IssueRequest(
        title="Calculation returns incorrect result",
        description=(
            "The calculator returns 1 but the expected "
            "result is 2."
        ),
        repository_path=str(repository),
    )


def test_debugging_workflow_runs_end_to_end(tmp_path):
    repository, source_file = create_calculator_repository(tmp_path)

    state = DebuggingState(
        issue=create_issue(repository)
    )

    workflow = build_workflow(FakeWorkflowLLM())

    result = workflow.run(
        state,
        top_k=3,
        validation_command=["pytest", "-q"],
    )

    assert result.analysis is not None
    assert result.analysis.issue_type.value == "bug"
    assert result.evidence

    assert result.root_cause is not None
    assert result.root_cause.affected_files == ["calculator.py"]

    assert result.proposed_fix is not None
    assert result.proposed_fix.patch

    assert result.validation is not None
    assert result.validation.passed is True
    assert result.validation.tests_run == 1
    assert result.validation.tests_passed == 1
    assert result.validation.tests_failed == 0

    assert result.validation_attempts == 1
    assert len(result.evidence) <= 3

    # The original repository must remain unchanged.
    assert source_file.read_text(encoding="utf-8") == (
        "def calculate():\n"
        "    return 1\n"
    )


def test_debugging_workflow_retries_failed_fix(tmp_path):
    repository, source_file = create_calculator_repository(tmp_path)

    state = DebuggingState(
        issue=create_issue(repository)
    )

    llm = RetryWorkflowLLM()
    workflow = build_workflow(llm)

    result = workflow.run(
        state,
        top_k=3,
        validation_command=["pytest", "-q"],
    )

    assert result.validation is not None
    assert result.validation.passed is True
    assert result.validation_attempts == 2
    assert llm.fix_calls == 2

    assert result.proposed_fix is not None
    assert "+    return 2" in result.proposed_fix.patch
    assert result.evidence

    # The original repository must remain unchanged.
    assert source_file.read_text(encoding="utf-8") == (
        "def calculate():\n"
        "    return 1\n"
    )


def test_workflow_reuses_embeddings_for_unchanged_repository(
    tmp_path,
):
    repository, _ = create_calculator_repository(tmp_path)

    document_embedding_provider = FakeEmbeddingProvider()

    workflow = build_workflow(
        FakeWorkflowLLM(),
        embedding_provider=document_embedding_provider,
    )

    first_state = DebuggingState(
        issue=create_issue(repository)
    )

    workflow.run(
        first_state,
        top_k=3,
        validation_command=["pytest", "-q"],
    )

    first_document_call_count = (
        document_embedding_provider.call_count
    )
    first_document_text_count = (
        document_embedding_provider.embedded_text_count
    )

    assert first_document_call_count > 0
    assert first_document_text_count > 0

    first_query_call_count = (
        workflow.test_query_embedding_provider.call_count
    )

    assert first_query_call_count > 0

    second_state = DebuggingState(
        issue=create_issue(repository)
    )

    workflow.run(
        second_state,
        top_k=3,
        validation_command=["pytest", "-q"],
    )

    # Unchanged repository documents must not be re-embedded.
    assert (
        document_embedding_provider.call_count
        == first_document_call_count
    )
    assert (
        document_embedding_provider.embedded_text_count
        == first_document_text_count
    )

    # Semantic search is still expected to embed new queries.
    assert (
        workflow.test_query_embedding_provider.call_count
        > first_query_call_count
    )

    assert second_state.evidence
    assert second_state.validation is not None
    assert second_state.validation.passed is True

