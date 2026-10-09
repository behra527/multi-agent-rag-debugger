import pytest

from app.rag.chunker import DocumentChunk
from app.rag.keyword_retriever import KeywordRetriever


def make_chunks() -> list[DocumentChunk]:
    return [
        DocumentChunk(
            content=(
                "def login(username, password):\n"
                "    return authenticate(username, password)"
            ),
            source="auth.py",
            language="python",
            chunk_index=0,
            start_line=1,
            end_line=2,
        ),
        DocumentChunk(
            content=(
                "def calculate_total(items):\n"
                "    return sum(items)"
            ),
            source="calculator.py",
            language="python",
            chunk_index=0,
            start_line=1,
            end_line=2,
        ),
        DocumentChunk(
            content=(
                "authentication error occurs during login"
            ),
            source="errors.md",
            language="markdown",
            chunk_index=0,
            start_line=1,
            end_line=1,
        ),
    ]


def test_keyword_retriever_returns_matching_chunks():
    retriever = KeywordRetriever()

    results = retriever.retrieve(
        "login authentication",
        make_chunks(),
    )

    assert results
    assert results[0][0].source == "errors.md"
    assert results[0][1] == 1.0


def test_keyword_retriever_ranks_by_match_score():
    retriever = KeywordRetriever()

    results = retriever.retrieve(
        "login authentication",
        make_chunks(),
    )

    assert results[0][1] >= results[1][1]


def test_keyword_retriever_respects_top_k():
    retriever = KeywordRetriever()

    results = retriever.retrieve(
        "login authentication",
        make_chunks(),
        top_k=1,
    )

    assert len(results) == 1


def test_keyword_retriever_rejects_empty_query():
    retriever = KeywordRetriever()

    with pytest.raises(
        ValueError,
        match="query must not be empty",
    ):
        retriever.retrieve(
            "",
            make_chunks(),
        )


def test_keyword_retriever_rejects_invalid_top_k():
    retriever = KeywordRetriever()

    with pytest.raises(
        ValueError,
        match="top_k must be greater than 0",
    ):
        retriever.retrieve(
            "login",
            make_chunks(),
            top_k=0,
        )


def test_keyword_retriever_returns_empty_for_no_match():
    retriever = KeywordRetriever()

    results = retriever.retrieve(
        "database migration",
        make_chunks(),
    )

    assert results == []