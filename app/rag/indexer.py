
import hashlib
from pathlib import Path

from app.rag.chunker import DocumentChunk, RepositoryChunker
from app.rag.embeddings import EmbeddingProvider
from app.rag.loader import RepositoryLoader
from app.rag.scanner import RepositoryScanner
from app.rag.vector_store import VectorStore


class RepositoryIndexer:
    """Build and cache a vector index for repository contents."""

    def __init__(
        self,
        scanner: RepositoryScanner,
        loader: RepositoryLoader,
        chunker: RepositoryChunker,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self.scanner = scanner
        self.loader = loader
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

        self.chunks: list[DocumentChunk] = []
        self._indexed_repository: Path | None = None
        self._indexed_fingerprint: str | None = None

    def index(
        self,
        repository_path: str | Path,
    ) -> int:
        """Index a repository, reusing its index if content is unchanged."""

        root = Path(repository_path).resolve()

        files = self.scanner.scan(root)
        loaded_files = self.loader.load(files)
        chunks = self.chunker.chunk(loaded_files)

        fingerprint = self._create_fingerprint(
            root,
            files,
        )

        if (
            self._indexed_repository == root
            and self._indexed_fingerprint == fingerprint
        ):
            return len(self.chunks)

        # Build embeddings before replacing the current index.
        # If embedding generation fails, the previous index remains intact.
        embeddings: list[list[float]] = []

        if chunks:
            texts = [chunk.content for chunk in chunks]
            embeddings = self.embedding_provider.embed(texts)

            if len(embeddings) != len(chunks):
                raise ValueError(
                    "Embedding count must match the number of chunks."
                )

        # Replace the index only after preparation succeeds.
        self.vector_store.clear()

        if chunks:
            self.vector_store.add(embeddings, chunks)

        self.chunks = chunks
        self._indexed_repository = root
        self._indexed_fingerprint = fingerprint

        return len(self.chunks)

    def get_chunks(self) -> list[DocumentChunk]:
        """Return a copy of the indexed chunks."""

        return list(self.chunks)

    @staticmethod
    def _create_fingerprint(
        repository_path: Path,
        files: list[Path],
    ) -> str:
        """Create a fingerprint from repository paths and file contents."""

        digest = hashlib.sha256()

        for file_path in sorted(files):
            relative_path = file_path.relative_to(
                repository_path
            ).as_posix()

            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\0")

            with file_path.open("rb") as file:
                for block in iter(
                    lambda: file.read(1024 * 1024),
                    b"",
                ):
                    digest.update(block)

            digest.update(b"\0")

        return digest.hexdigest()