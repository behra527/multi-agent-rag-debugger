from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.domain.schemas import RetrievedChunk
from app.rag.bm25 import tokenize


def rerank_results(query: str, results: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
    if settings.reranker == "cross_encoder":
        return cross_encoder_rerank(query, results, top_k)
    return simple_rerank(query, results, top_k)


def simple_rerank(query: str, results: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
    """Lexical overlap reranker used when a cross-encoder is not configured."""
    query_terms = set(tokenize(query))
    rescored: list[RetrievedChunk] = []
    for item in results:
        chunk_terms = set(tokenize(item.chunk.content))
        overlap = len(query_terms & chunk_terms) / len(query_terms) if query_terms else 0.0
        combined = 0.65 * item.score + 0.35 * overlap
        rescored.append(item.model_copy(update={"rerank_score": combined, "score": combined}))
    rescored.sort(key=lambda row: row.score, reverse=True)
    return rescored[:top_k]


def cross_encoder_rerank(query: str, results: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise ProviderError("sentence-transformers is required for cross_encoder reranking.") from exc
    if not results:
        return []
    try:
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        pairs = [(query, item.chunk.content) for item in results]
        scores = model.predict(pairs)
    except Exception as exc:
        raise ProviderError(f"Cross-encoder rerank failed: {exc}") from exc
    rescored = [
        item.model_copy(update={"rerank_score": float(score), "score": float(score)})
        for item, score in zip(results, scores)
    ]
    rescored.sort(key=lambda row: row.score, reverse=True)
    return rescored[:top_k]
