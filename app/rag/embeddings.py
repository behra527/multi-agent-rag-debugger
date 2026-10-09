from abc import ABC, abstractmethod

from sentence_transformers import SentenceTransformer


class EmbeddingProvider(ABC):
    """Interface for converting text into vector embeddings."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Convert a list of texts into embeddings."""
        raise NotImplementedError


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformer embedding provider."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
        )

        return embeddings.tolist()