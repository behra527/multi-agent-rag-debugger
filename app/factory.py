
from app.agents.fix import FixAgent
from app.agents.issue_analyzer import IssueAnalyzer
from app.agents.root_cause import RootCauseAgent
from app.core.debugging_workflow import DebuggingWorkflow
from app.core.graph_workflow import GraphDebuggingWorkflow
from app.core.project_manager import ProjectManager
from app.core.supervisor import Supervisor
from app.llm.factory import get_llm_client
from app.rag.chunker import RepositoryChunker
from app.rag.embeddings import get_embedding_provider
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


def create_project_manager(
    use_langgraph: bool = False,
    provider: str | None = None,
) -> ProjectManager:
    """Build a fresh debugging application for each request.

    A new instance is created per call to ensure that each repository debugging
    session gets its own isolated VectorStore, RepositoryIndexer, and LLM client.
    Sharing these objects across repositories would cause cross-repo contamination.

    The RepositoryIndexer itself uses content-based fingerprinting to avoid
    redundant re-indexing of the same repository within a single session.
    """

    llm = get_llm_client(provider)
    embedding_provider = get_embedding_provider()
    vector_store = VectorStore(dimension=embedding_provider.dimension)

    indexer = RepositoryIndexer(
        scanner=RepositoryScanner(),
        loader=RepositoryLoader(),
        chunker=RepositoryChunker(),
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    vector_retriever = RepositoryRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    retriever = HybridRetriever(
        keyword_retriever=KeywordRetriever(),
        vector_retriever=vector_retriever,
    )

    validation_service = ValidationService(
        patcher=PatchApplier(),
        test_runner=TestRunner(),
    )

    if use_langgraph:
        workflow = GraphDebuggingWorkflow(
            issue_analyzer=IssueAnalyzer(llm),
            indexer=indexer,
            retriever=retriever,
            root_cause_agent=RootCauseAgent(llm),
            fix_agent=FixAgent(llm),
            validation_service=validation_service,
            evidence_ranker=EvidenceRanker(),
        )
    else:
        workflow = DebuggingWorkflow(
            issue_analyzer=IssueAnalyzer(llm),
            indexer=indexer,
            retriever=retriever,
            root_cause_agent=RootCauseAgent(llm),
            fix_agent=FixAgent(llm),
            validation_service=validation_service,
            supervisor=Supervisor(),
            evidence_ranker=EvidenceRanker(),
        )

    return ProjectManager(workflow=workflow)


def create_repair_orchestrator(provider: str | None = None):
    from app.repair.agents import CodeRepairEngineer, QAEngineer, RepositoryInvestigator
    from app.repair.orchestrator import RepairOrchestrator

    llm = get_llm_client(provider)
    embedding_provider = get_embedding_provider()
    vector_store = VectorStore(dimension=embedding_provider.dimension)
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
    patcher = PatchApplier()
    validation_service = ValidationService(patcher=patcher, test_runner=TestRunner())
    return RepairOrchestrator(
        investigator=RepositoryInvestigator(llm, indexer, retriever, EvidenceRanker()),
        repair_engineer=CodeRepairEngineer(llm),
        qa=QAEngineer(validation_service, patcher),
    )


def create_graph_project_manager(provider: str | None = None) -> ProjectManager:
    """Convenience helper to instantiate a LangGraph-orchestrated project manager."""
    return create_project_manager(use_langgraph=True, provider=provider)
