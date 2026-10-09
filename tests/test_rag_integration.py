from app.rag.chunker import RepositoryChunker
from app.rag.embeddings import LocalEmbeddingProvider
from app.rag.indexer import RepositoryIndexer
from app.rag.loader import RepositoryLoader
from app.rag.retriever import RepositoryRetriever
from app.rag.scanner import RepositoryScanner
from app.rag.vector_store import VectorStore


def test_real_semantic_retrieval():
    embedding_provider = LocalEmbeddingProvider()

    vector_store = VectorStore(dimension=384)

    indexer = RepositoryIndexer(
        scanner=RepositoryScanner(),
        loader=RepositoryLoader(),
        chunker=RepositoryChunker(chunk_size=20),
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    count = indexer.index("data/sample_project")

    assert count > 0

    retriever = RepositoryRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    result = retriever.retrieve(
        "login authentication error",
        top_k=3,
    )

    assert len(result.documents) > 0

    assert any(
        "login" in document.content.lower()
        for document in result.documents
    )