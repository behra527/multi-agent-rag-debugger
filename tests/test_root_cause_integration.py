
from app.agents.root_cause import RootCauseAgent
from app.core.models import (
    IssueAnalysis,
    IssuePriority,
    IssueRequest,
    IssueType,
)
from app.llm.interface import LLMClient
from app.rag.chunker import RepositoryChunker
from app.rag.embeddings import LocalEmbeddingProvider
from app.rag.indexer import RepositoryIndexer
from app.rag.loader import RepositoryLoader
from app.rag.retriever import RepositoryRetriever
from app.rag.scanner import RepositoryScanner
from app.rag.vector_store import VectorStore


class FakeRootCauseLLM(LLMClient):
    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        assert "Login authentication error" in prompt
        assert "login.py" in prompt
        assert "def login" in prompt
        assert system_prompt is not None

        return """
        {
            "root_cause": "The login function only checks whether username and password values are present.",
            "explanation": "The retrieved login implementation does not verify whether the supplied credentials are valid.",
            "affected_files": ["login.py"],
            "evidence": [
                "login.py contains the login function.",
                "The function returns True when username and password are non-empty."
            ],
            "confidence": 0.88
        }
        """


def test_real_rag_to_root_cause_pipeline():
    embedding_provider = LocalEmbeddingProvider()

    vector_store = VectorStore(dimension=384)

    indexer = RepositoryIndexer(
        scanner=RepositoryScanner(),
        loader=RepositoryLoader(),
        chunker=RepositoryChunker(chunk_size=20),
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    indexed_chunks = indexer.index(
        "data/sample_project"
    )

    assert indexed_chunks > 0

    retriever = RepositoryRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    retrieval_result = retriever.retrieve(
        "login authentication error",
        top_k=3,
    )

    evidence = retriever.to_evidence(
        retrieval_result
    )

    assert evidence
    assert any(
        "login.py" in item.source
        for item in evidence
    )

    issue = IssueRequest(
        title="Login authentication error",
        description=(
            "Users report that login authentication "
            "is not working correctly."
        ),
        repository_path="data/sample_project",
    )

    analysis = IssueAnalysis(
        issue_type=IssueType.ERROR,
        priority=IssuePriority.HIGH,
        summary="Login authentication is failing.",
        affected_components=["login"],
        search_queries=["login authentication error"],
    )

    agent = RootCauseAgent(
        llm=FakeRootCauseLLM()
    )

    result = agent.analyze(
        issue=issue,
        analysis=analysis,
        evidence=evidence,
    )

    assert result.root_cause
    assert result.explanation
    assert "login.py" in result.affected_files
    assert 0.0 <= result.confidence <= 1.0

