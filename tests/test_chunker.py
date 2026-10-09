from app.rag.chunker import RepositoryChunker
from app.rag.loader import RepositoryLoader
from app.rag.scanner import RepositoryScanner


def get_loaded_files():
    scanner = RepositoryScanner()
    loader = RepositoryLoader()

    files = scanner.scan("data/sample_project")

    return loader.load(files)


def test_chunker_creates_chunks():
    loaded_files = get_loaded_files()

    chunker = RepositoryChunker(chunk_size=3)

    chunks = chunker.chunk(loaded_files)

    assert len(chunks) > 0


def test_chunk_contains_source_and_line_metadata():
    loaded_files = get_loaded_files()

    chunker = RepositoryChunker(chunk_size=3)

    chunks = chunker.chunk(loaded_files)

    login_chunk = next(
        chunk
        for chunk in chunks
        if chunk.language == "python"
    )

    assert login_chunk.source.endswith("login.py")
    assert login_chunk.start_line >= 1
    assert login_chunk.end_line >= login_chunk.start_line
    assert login_chunk.chunk_index == 0


def test_chunk_size_is_respected():
    loaded_files = get_loaded_files()

    chunker = RepositoryChunker(chunk_size=3)

    chunks = chunker.chunk(loaded_files)

    for chunk in chunks:
        lines = chunk.content.splitlines()

        assert len(lines) <= 3


def test_chunker_rejects_invalid_chunk_size():
    try:
        RepositoryChunker(chunk_size=0)
        assert False, "Expected ValueError"
    except ValueError:
        pass