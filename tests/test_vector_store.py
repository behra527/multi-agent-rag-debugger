import pytest

from app.rag.chunker import DocumentChunk
from app.rag.vector_store import VectorStore


def create_chunk(index: int) -> DocumentChunk:
    return DocumentChunk(
        content=f"chunk {index}",
        source="login.py",
        language="python",
        chunk_index=index,
        start_line=index + 1,
        end_line=index + 1,
    )


def test_vector_store_adds_and_searches_chunks():
    store = VectorStore(dimension=3)

    chunks = [
        create_chunk(0),
        create_chunk(1),
    ]

    embeddings = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ]

    store.add(embeddings, chunks)

    results = store.search(
        [1.0, 0.0, 0.0],
        top_k=1,
    )

    assert len(results) == 1
    assert results[0][0].content == "chunk 0"
    assert results[0][1] > 0.9


def test_vector_store_rejects_mismatched_lengths():
    store = VectorStore(dimension=3)

    chunks = [create_chunk(0)]

    with pytest.raises(
        ValueError,
        match="match number of chunks",
    ):
        store.add(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            chunks,
        )


def test_vector_store_rejects_wrong_dimension():
    store = VectorStore(dimension=3)

    with pytest.raises(
        ValueError,
        match="Expected vectors with dimension 3",
    ):
        store.add(
            [[1.0, 0.0]],
            [create_chunk(0)],
        )


def test_empty_store_returns_no_results():
    store = VectorStore(dimension=3)

    results = store.search(
        [1.0, 0.0, 0.0],
        top_k=5,
    )

    assert results == []


def test_vector_store_rejects_invalid_top_k():
    store = VectorStore(dimension=3)

    with pytest.raises(
        ValueError,
        match="top_k",
    ):
        store.search(
            [1.0, 0.0, 0.0],
            top_k=0,
        )


def test_vector_store_clear_removes_vectors_and_chunks():
    store = VectorStore(dimension=3)

    chunks = [
        create_chunk(0),
        create_chunk(1),
    ]

    embeddings = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ]

    store.add(
        embeddings,
        chunks,
    )

    assert len(store.chunks) == 2
    assert store.index.ntotal == 2

    store.clear()

    assert len(store.chunks) == 0
    assert store.index.ntotal == 0

    results = store.search(
        [1.0, 0.0, 0.0],
        top_k=5,
    )

    assert results == []


def test_vector_store_can_be_reused_after_clear():
    store = VectorStore(dimension=3)

    first_chunk = create_chunk(0)
    second_chunk = create_chunk(1)

    store.add(
        [[1.0, 0.0, 0.0]],
        [first_chunk],
    )

    store.clear()

    store.add(
        [[0.0, 1.0, 0.0]],
        [second_chunk],
    )

    assert len(store.chunks) == 1
    assert store.index.ntotal == 1

    results = store.search(
        [0.0, 1.0, 0.0],
        top_k=5,
    )

    assert len(results) == 1
    assert results[0][0].content == "chunk 1"
    assert results[0][1] > 0.9