from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import numpy as np

from app.core.config import settings
from app.core.exceptions import ConfigurationError, ProviderError


class EmbeddingProvider(ABC):
    """Interface for converting text into vector embeddings."""

    model_name: str
    dimension: int
    provider_name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Convert a list of texts into embeddings."""
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashing embeddings for tests and fully offline CI.

    This is not a semantic model. Production deployments should use `local` or `openai`.
    """

    def __init__(self, dimension: int | None = None) -> None:
        self.provider_name = "hash"
        self.model_name = "hash-sha256"
        self.dimension = dimension or settings.embedding_dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            raw = np.frombuffer((digest * ((self.dimension // len(digest)) + 1))[: self.dimension], dtype=np.uint8)
            vec = raw.astype(np.float32)
            vec = vec - vec.mean()
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec.tolist())
        return vectors


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformer embedding provider."""

    def __init__(
        self,
        model_name: str | None = None,
    ) -> None:
        self.provider_name = "local"
        self.model_name = model_name or settings.embedding_model
        self._model = None
        self.dimension = settings.embedding_dimension

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            dim_fn = getattr(self._model, "get_embedding_dimension", None) or getattr(
                self._model, "get_sentence_embedding_dimension"
            )
            self.dimension = int(dim_fn())
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str | None = None) -> None:
        if not settings.openai_api_key:
            raise ConfigurationError("OPENAI_API_KEY is required for OpenAI embeddings.")
        from openai import OpenAI

        self.provider_name = "openai"
        self.model_name = model_name or settings.openai_embedding_model
        self.dimension = 1536 if "small" in self.model_name else 3072
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self.client.embeddings.create(model=self.model_name, input=texts)
        except Exception as exc:
            raise ProviderError(f"OpenAI embeddings failed: {exc}") from exc
        vectors = [item.embedding for item in response.data]
        if vectors:
            self.dimension = len(vectors[0])
        return vectors


def get_embedding_provider(provider: str | None = None, model_name: str | None = None) -> EmbeddingProvider:
    selected = (provider or settings.embedding_provider).lower().strip()
    if selected == "hash":
        return HashEmbeddingProvider()
    if selected == "openai":
        return OpenAIEmbeddingProvider(model_name=model_name)
    if selected == "local":
        return LocalEmbeddingProvider(model_name=model_name)
    raise ConfigurationError(
        f"Unknown embedding provider '{selected}'. Use local, hash, or openai."
    )
