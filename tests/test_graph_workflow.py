from pathlib import Path

from app.agents.fix import FixAgent
from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.root_cause import RootCauseAgent
from app.core.graph_workflow import GraphDebuggingWorkflow
from app.core.models import IssueRequest
from app.core.workflow import DebuggingState
from app.llm.mock_provider import MockLLMClient
from app.rag.chunker import RepositoryChunker
from app.rag.embeddings import LocalEmbeddingProvider
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


def test_graph_debugging_workflow_runs_end_to_end(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    (repo / "test_calculator.py").write_text(
        "from calculator import calculate\ndef test_calculate():\n    assert calculate() == 2\n",
        encoding="utf-8",
    )

    llm = MockLLMClient()
    embedding_provider = LocalEmbeddingProvider()
    vector_store = VectorStore(dimension=384)

    indexer = RepositoryIndexer(
        scanner=RepositoryScanner(),
        loader=RepositoryLoader(),
        chunker=RepositoryChunker(),
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )
    retriever = HybridRetriever(
        keyword_retriever=KeywordRetriever(),
        vector_retriever=RepositoryRetriever(
            embedding_provider=embedding_provider,
            vector_store=vector_store,
        ),
    )

    workflow = GraphDebuggingWorkflow(
        issue_analyzer=IssueAnalyzer(llm),
        indexer=indexer,
        retriever=retriever,
        root_cause_agent=RootCauseAgent(llm),
        fix_agent=FixAgent(llm),
        validation_service=ValidationService(
            patcher=PatchApplier(),
            test_runner=TestRunner(),
        ),
    )

    issue = IssueRequest(
        title="Calculator bug",
        description="calculate() returns 1 instead of 2",
        repository_path=str(repo),
    )
    state = DebuggingState(issue=issue)

    final_state = workflow.run(state, top_k=2)

    assert final_state.analysis is not None
    assert final_state.evidence
    assert final_state.root_cause is not None
    assert final_state.proposed_fix is not None
    assert final_state.validation is not None
    assert final_state.validation.passed is True
    assert len(final_state.stage_traces) >= 5
