from app.rag.embeddings import EmbeddingProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]


def test_embedding_provider_returns_vectors():
    provider = FakeEmbeddingProvider()

    result = provider.embed(["hello", "hello world"])

    assert result == [[5.0], [11.0]]


def test_embedding_provider_handles_empty_input():
    provider = FakeEmbeddingProvider()

    result = provider.embed([])

    assert result == []