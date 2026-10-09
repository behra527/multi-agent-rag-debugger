import numpy as np
import faiss

from app.rag.chunker import DocumentChunk


class VectorStore:
    """FAISS-backed vector store for repository chunks."""

    def __init__(
        self,
        dimension: int,
    ) -> None:
        if dimension <= 0:
            raise ValueError(
                "dimension must be greater than 0."
            )

        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.chunks: list[DocumentChunk] = []

    def add(
        self,
        embeddings: list[list[float]],
        chunks: list[DocumentChunk],
    ) -> None:
        """Add embeddings and their corresponding chunks."""

        if len(embeddings) != len(chunks):
            raise ValueError(
                "embeddings and chunks must match number of chunks."
            )

        if not embeddings:
            return

        vectors = np.asarray(
            embeddings,
            dtype=np.float32,
        )

        if vectors.ndim != 2:
            raise ValueError(
                "embeddings must be a 2D array."
            )

        if vectors.shape[1] != self.dimension:
            raise ValueError(
                f"Expected vectors with dimension {self.dimension}."
            )

        faiss.normalize_L2(vectors)

        self.index.add(vectors)
        self.chunks.extend(chunks)

    def clear(self) -> None:
        """Remove all stored vectors and associated chunks."""

        self.index.reset()
        self.chunks.clear()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        """Search for the most similar stored chunks."""

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than 0."
            )

        if not self.chunks:
            return []

        query = np.asarray(
            [query_embedding],
            dtype=np.float32,
        )

        if query.ndim != 2:
            raise ValueError(
                "query_embedding must be a 1D vector."
            )

        if query.shape[1] != self.dimension:
            raise ValueError(
                f"Expected query vector with dimension "
                f"{self.dimension}."
            )

        faiss.normalize_L2(query)

        limit = min(
            top_k,
            len(self.chunks),
        )

        scores, indices = self.index.search(
            query,
            limit,
        )

        results: list[
            tuple[DocumentChunk, float]
        ] = []

        for score, index in zip(
            scores[0],
            indices[0],
        ):
            if index < 0:
                continue

            results.append(
                (
                    self.chunks[index],
                    float(score),
                )
            )

        return results