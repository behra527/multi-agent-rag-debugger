from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from app.core.config import settings
from app.domain.schemas import TextChunk


class PersistentDocumentIndex:
    """FAISS index plus chunk metadata persisted per knowledge base."""

    def __init__(self, knowledge_base_id: str, dimension: int, workspace_id: str) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be greater than 0.")
        self.knowledge_base_id = knowledge_base_id
        self.workspace_id = workspace_id
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.chunks: list[TextChunk] = []
        self.directory = settings.index_dir / workspace_id / knowledge_base_id
        self.directory.mkdir(parents=True, exist_ok=True)

    @property
    def faiss_path(self) -> Path:
        return self.directory / "index.faiss"

    @property
    def chunks_path(self) -> Path:
        return self.directory / "chunks.json"

    def add(self, embeddings: list[list[float]], chunks: list[TextChunk]) -> None:
        if len(embeddings) != len(chunks):
            raise ValueError("embeddings and chunks must have the same length.")
        if not embeddings:
            return
        vectors = np.asarray(embeddings, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[1] != self.dimension:
            raise ValueError(f"Expected 2D embeddings with dimension {self.dimension}.")
        faiss.normalize_L2(vectors)
        self.index.add(vectors)
        self.chunks.extend(chunks)

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[TextChunk, float]]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0.")
        if not self.chunks:
            return []
        query = np.asarray([query_embedding], dtype=np.float32)
        if query.shape[1] != self.dimension:
            raise ValueError(f"Expected query vector with dimension {self.dimension}.")
        faiss.normalize_L2(query)
        limit = min(top_k, len(self.chunks))
        scores, indices = self.index.search(query, limit)
        results: list[tuple[TextChunk, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            results.append((self.chunks[idx], float(score)))
        return results

    def save(self) -> None:
        faiss.write_index(self.index, str(self.faiss_path))
        payload = [chunk.model_dump() for chunk in self.chunks]
        self.chunks_path.write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, knowledge_base_id: str, dimension: int, workspace_id: str) -> "PersistentDocumentIndex":
        store = cls(knowledge_base_id, dimension, workspace_id)
        if store.faiss_path.exists() and store.chunks_path.exists():
            store.index = faiss.read_index(str(store.faiss_path))
            raw = json.loads(store.chunks_path.read_text(encoding="utf-8"))
            store.chunks = [TextChunk.model_validate(item) for item in raw]
            store.dimension = store.index.d
        return store

    def delete(self) -> None:
        if self.faiss_path.exists():
            self.faiss_path.unlink()
        if self.chunks_path.exists():
            self.chunks_path.unlink()
        self.index = faiss.IndexFlatIP(self.dimension)
        self.chunks.clear()
