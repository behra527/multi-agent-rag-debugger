from app.rag.chunker import DocumentChunk
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.retriever import RepositoryRetriever
from app.rag.vector_store import VectorStore


class FakeEmbeddingProvider:
    """Deterministic embedding provider for hybrid tests."""

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [
            [1.0, 0.0]
            for _ in texts
        ]


def make_chunks() -> list[DocumentChunk]:
    return [
        DocumentChunk(
            content=(
                "login authentication error"
            ),
            source="auth.py",
            language="python",
            chunk_index=0,
            start_line=1,
            end_line=1,
        ),
        DocumentChunk(
            content=(
                "database connection configuration"
            ),
            source="database.py",
            language="python",
            chunk_index=0,
            start_line=1,
            end_line=1,
        ),
    ]


def build_retriever(
    chunks: list[DocumentChunk],
) -> RepositoryRetriever:
    embedding_provider = FakeEmbeddingProvider()

    vector_store = VectorStore(
        dimension=2
    )

    vector_store.add(
        embedding_provider.embed(
            [chunk.content for chunk in chunks]
        ),
        chunks,
    )

    return RepositoryRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )


def build_hybrid_retriever(
    chunks: list[DocumentChunk],
) -> HybridRetriever:
    return HybridRetriever(
        keyword_retriever=KeywordRetriever(),
        vector_retriever=build_retriever(chunks),
    )


def test_hybrid_retriever_combines_results():
    chunks = make_chunks()

    retriever = build_hybrid_retriever(
        chunks
    )

    results = retriever.retrieve(
        "login authentication",
        chunks,
    )

    assert results
    assert results[0][0].source == "auth.py"


def test_hybrid_retriever_returns_ranked_scores():
    chunks = make_chunks()

    retriever = build_hybrid_retriever(
        chunks
    )

    results = retriever.retrieve(
        "login authentication",
        chunks,
    )

    assert results
    assert results[0][1] >= results[-1][1]


def test_hybrid_retriever_uses_rank_based_scores():
    chunks = make_chunks()

    retriever = build_hybrid_retriever(
        chunks
    )

    results = retriever.retrieve(
        "login authentication",
        chunks,
    )

    assert results

    # Keyword retriever:
    # auth.py = rank 1 -> 1.0
    #
    # Semantic retriever:
    # Both chunks have identical fake embeddings.
    # auth.py is therefore rank 2 -> 0.5
    #
    # Hybrid score:
    # (0.4 * 1.0) + (0.6 * 0.5) = 0.7

    expected_top_score = 0.7

    assert results[0][1] == expected_top_score


def test_hybrid_retriever_returns_empty_for_no_chunks():
    chunks: list[DocumentChunk] = []

    retriever = build_hybrid_retriever(
        chunks
    )

    results = retriever.retrieve(
        "login authentication",
        chunks,
    )

    assert results == []


def test_hybrid_retriever_respects_top_k():
    chunks = make_chunks()

    retriever = build_hybrid_retriever(
        chunks
    )

    results = retriever.retrieve(
        "login authentication",
        chunks,
        top_k=1,
    )

    assert len(results) == 1


def test_hybrid_retriever_rejects_empty_query():
    chunks = make_chunks()

    retriever = build_hybrid_retriever(
        chunks
    )

    try:
        retriever.retrieve(
            "",
            chunks,
        )
    except ValueError as exc:
        assert (
            "query must not be empty"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_hybrid_retriever_rejects_invalid_top_k():
    chunks = make_chunks()

    retriever = build_hybrid_retriever(
        chunks
    )

    try:
        retriever.retrieve(
            "login authentication",
            chunks,
            top_k=0,
        )
    except ValueError as exc:
        assert (
            "top_k must be greater than 0"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_hybrid_retriever_normalizes_weights():
    chunks = make_chunks()

    retriever = HybridRetriever(
        keyword_retriever=KeywordRetriever(),
        vector_retriever=build_retriever(chunks),
        keyword_weight=2.0,
        vector_weight=3.0,
    )

    assert retriever.keyword_weight == 0.4
    assert retriever.vector_weight == 0.6


def test_hybrid_retriever_rejects_zero_weights():
    chunks = make_chunks()

    try:
        HybridRetriever(
            keyword_retriever=KeywordRetriever(),
            vector_retriever=build_retriever(chunks),
            keyword_weight=0.0,
            vector_weight=0.0,
        )
    except ValueError as exc:
        assert (
            "At least one retrieval weight"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )