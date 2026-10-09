
from app.rag.chunker import DocumentChunk
from app.rag.embeddings import EmbeddingProvider
from app.rag.indexer import RepositoryIndexer
from app.rag.loader import RepositoryLoader
from app.rag.retriever import RepositoryRetriever
from app.rag.scanner import RepositoryScanner
from app.rag.vector_store import VectorStore


class FakeEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0, 0.0]
            for _ in texts
        ]


def create_chunk() -> DocumentChunk:
    return DocumentChunk(
        content="def login(): return True",
        source="login.py",
        language="python",
        chunk_index=0,
        start_line=1,
        end_line=1,
    )


def test_retriever_returns_relevant_documents():
    embedding_provider = FakeEmbeddingProvider()
    vector_store = VectorStore(dimension=3)

    vector_store.add(
        [[1.0, 0.0, 0.0]],
        [create_chunk()],
    )

    retriever = RepositoryRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    result = retriever.retrieve(
        "login authentication error",
        top_k=1,
    )

    assert result.query == "login authentication error"
    assert len(result.documents) == 1
    assert result.documents[0].source == "login.py"
    assert result.documents[0].metadata["language"] == "python"


def test_retriever_rejects_empty_query():
    embedding_provider = FakeEmbeddingProvider()
    vector_store = VectorStore(dimension=3)

    retriever = RepositoryRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    try:
        retriever.retrieve("")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_retriever_converts_documents_to_evidence():
    embedding_provider = FakeEmbeddingProvider()
    vector_store = VectorStore(dimension=3)

    indexer = RepositoryIndexer(
        scanner=RepositoryScanner(),
        loader=RepositoryLoader(),
        chunker=__import__(
            "app.rag.chunker",
            fromlist=["RepositoryChunker"],
        ).RepositoryChunker(chunk_size=20),
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    indexer.index("data/sample_project")

    retriever = RepositoryRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    result = retriever.retrieve(
        "login authentication",
        top_k=2,
    )

    evidence = retriever.to_evidence(result)

    assert len(evidence) > 0
    assert evidence[0].source
    assert evidence[0].content
    assert evidence[0].start_line >= 1
    assert evidence[0].end_line >= evidence[0].start_line
    assert evidence[0].language

