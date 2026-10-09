
from app.rag.chunker import RepositoryChunker
from app.rag.embeddings import EmbeddingProvider
from app.rag.indexer import RepositoryIndexer
from app.rag.loader import RepositoryLoader
from app.rag.scanner import RepositoryScanner
from app.rag.vector_store import VectorStore


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider for indexer tests."""

    def __init__(self):
        self.call_count = 0
        self.embedded_text_count = 0

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        self.call_count += 1
        self.embedded_text_count += len(texts)

        return [
            [1.0, 0.0, 0.0]
            for _ in texts
        ]


def create_indexer() -> tuple[RepositoryIndexer, VectorStore]:
    """Create an indexer with deterministic test dependencies."""

    vector_store = VectorStore(dimension=3)
    embedding_provider = FakeEmbeddingProvider()

    indexer = RepositoryIndexer(
        scanner=RepositoryScanner(),
        loader=RepositoryLoader(),
        chunker=RepositoryChunker(chunk_size=3),
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    return indexer, vector_store


def test_indexer_builds_repository_index():
    indexer, vector_store = create_indexer()

    count = indexer.index("data/sample_project")

    assert count > 0
    assert len(vector_store.chunks) == count
    assert vector_store.index.ntotal == count


def test_indexer_handles_empty_repository(tmp_path):
    indexer, vector_store = create_indexer()

    count = indexer.index(tmp_path)

    assert count == 0
    assert vector_store.chunks == []
    assert vector_store.index.ntotal == 0


def test_indexer_exposes_indexed_chunks():
    indexer, vector_store = create_indexer()

    count = indexer.index("data/sample_project")
    chunks = indexer.get_chunks()

    assert count == len(chunks)
    assert chunks
    assert len(vector_store.chunks) == count


def test_indexer_reindex_does_not_duplicate_vectors():
    indexer, vector_store = create_indexer()

    first_count = indexer.index("data/sample_project")
    second_count = indexer.index("data/sample_project")

    assert first_count > 0
    assert second_count == first_count
    assert len(vector_store.chunks) == second_count
    assert vector_store.index.ntotal == second_count


def test_indexer_replaces_previous_index_when_repository_changes(
    tmp_path,
):
    repository = tmp_path / "project"
    repository.mkdir()

    first_file = repository / "first.py"
    first_file.write_text(
        "def first():\n"
        "    return 1\n"
        "    return 2\n",
        encoding="utf-8",
    )

    indexer, vector_store = create_indexer()
    first_count = indexer.index(repository)

    second_file = repository / "second.py"
    second_file.write_text(
        "def second():\n"
        "    return 3\n"
        "    return 4\n",
        encoding="utf-8",
    )

    second_count = indexer.index(repository)

    assert first_count > 0
    assert second_count > first_count
    assert vector_store.index.ntotal == second_count
    assert len(vector_store.chunks) == second_count

    indexed_sources = {
        chunk.source for chunk in vector_store.chunks
    }

    assert any(
        source.endswith("first.py")
        for source in indexed_sources
    )
    assert any(
        source.endswith("second.py")
        for source in indexed_sources
    )


def test_indexer_refreshes_changed_repository(tmp_path):
    repository = tmp_path / "project"
    repository.mkdir()

    source_file = repository / "app.py"
    source_file.write_text(
        "def first():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    indexer, vector_store = create_indexer()
    embedding_provider = indexer.embedding_provider

    first_count = indexer.index(repository)
    first_call_count = embedding_provider.call_count

    assert first_count > 0
    assert first_call_count > 0

    source_file.write_text(
        "def second():\n"
        "    return 2\n"
        "    return 3\n"
        "    return 4\n",
        encoding="utf-8",
    )

    second_count = indexer.index(repository)

    assert second_count > 0
    assert embedding_provider.call_count > first_call_count

    assert any(
        "second" in chunk.content
        for chunk in indexer.get_chunks()
    )

    assert not any(
        "first" in chunk.content
        for chunk in indexer.get_chunks()
    )

    assert len(vector_store.chunks) == second_count
    assert vector_store.index.ntotal == second_count


def test_indexer_returns_a_copy_of_chunks():
    indexer, _ = create_indexer()

    indexer.index("data/sample_project")

    original_count = len(indexer.get_chunks())
    returned_chunks = indexer.get_chunks()
    returned_chunks.clear()

    assert len(indexer.get_chunks()) == original_count


def test_indexer_reuses_embeddings_for_unchanged_repository(
    tmp_path,
):
    repository = tmp_path / "project"
    repository.mkdir()

    source_file = repository / "app.py"
    source_file.write_text(
        "def hello():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    indexer, vector_store = create_indexer()
    embedding_provider = indexer.embedding_provider

    first_count = indexer.index(repository)
    first_call_count = embedding_provider.call_count
    first_text_count = embedding_provider.embedded_text_count

    second_count = indexer.index(repository)

    assert first_count > 0
    assert second_count == first_count
    assert embedding_provider.call_count == first_call_count
    assert embedding_provider.embedded_text_count == first_text_count
    assert vector_store.index.ntotal == second_count


def test_indexer_rebuilds_index_when_file_is_deleted(tmp_path):
    repository = tmp_path / "project"
    repository.mkdir()

    first_file = repository / "first.py"
    first_file.write_text(
        "def first():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    second_file = repository / "second.py"
    second_file.write_text(
        "def second():\n"
        "    return 2\n",
        encoding="utf-8",
    )

    indexer, vector_store = create_indexer()
    embedding_provider = indexer.embedding_provider

    first_count = indexer.index(repository)
    first_call_count = embedding_provider.call_count

    assert first_count > 0

    first_file.unlink()

    second_count = indexer.index(repository)

    assert second_count > 0
    assert embedding_provider.call_count > first_call_count

    indexed_sources = {
        chunk.source for chunk in indexer.get_chunks()
    }

    assert not any(
        source.endswith("first.py")
        for source in indexed_sources
    )
    assert any(
        source.endswith("second.py")
        for source in indexed_sources
    )

    assert len(vector_store.chunks) == second_count
    assert vector_store.index.ntotal == second_count

