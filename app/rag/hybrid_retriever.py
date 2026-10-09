from app.rag.chunker import DocumentChunk
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.retriever import RepositoryRetriever


class HybridRetriever:
    """Combines keyword and semantic retrieval using rank fusion."""

    def __init__(
        self,
        keyword_retriever: KeywordRetriever,
        vector_retriever: RepositoryRetriever,
        *,
        keyword_weight: float = 0.4,
        vector_weight: float = 0.6,
    ) -> None:
        if keyword_weight < 0:
            raise ValueError(
                "keyword_weight must not be negative."
            )

        if vector_weight < 0:
            raise ValueError(
                "vector_weight must not be negative."
            )

        if keyword_weight + vector_weight == 0:
            raise ValueError(
                "At least one retrieval weight must be greater than 0."
            )

        total = keyword_weight + vector_weight

        self.keyword_weight = (
            keyword_weight / total
        )

        self.vector_weight = (
            vector_weight / total
        )

        self.keyword_retriever = keyword_retriever
        self.vector_retriever = vector_retriever

    def retrieve(
        self,
        query: str,
        chunks: list[DocumentChunk],
        *,
        top_k: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        """Retrieve and rank chunks using hybrid rank fusion."""

        if not query.strip():
            raise ValueError(
                "query must not be empty."
            )

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than 0."
            )

        if not chunks:
            return []

        keyword_results = (
            self.keyword_retriever.retrieve(
                query,
                chunks,
                top_k=top_k,
            )
        )

        vector_result = (
            self.vector_retriever.retrieve(
                query,
                top_k=top_k,
            )
        )

        vector_results = [
            (
                self._find_chunk(
                    chunks,
                    document.source,
                    document.content,
                ),
                document.score,
            )
            for document in vector_result.documents
        ]

        keyword_rank_scores = self._rank_scores(
            keyword_results
        )

        valid_vector_results = [
            (chunk, score)
            for chunk, score in vector_results
            if chunk is not None
        ]

        vector_rank_scores = self._rank_scores(
            valid_vector_results
        )

        all_chunks: dict[str, DocumentChunk] = {}

        for chunk, _ in keyword_results:
            all_chunks[self._chunk_key(chunk)] = chunk

        for chunk, _ in valid_vector_results:
            all_chunks[self._chunk_key(chunk)] = chunk

        ranked_results: list[
            tuple[DocumentChunk, float]
        ] = []

        for key, chunk in all_chunks.items():
            keyword_score = keyword_rank_scores.get(
                key,
                0.0,
            )

            vector_score = vector_rank_scores.get(
                key,
                0.0,
            )

            hybrid_score = (
                self.keyword_weight * keyword_score
                + self.vector_weight * vector_score
            )

            ranked_results.append(
                (
                    chunk,
                    hybrid_score,
                )
            )

        ranked_results.sort(
            key=lambda item: (
                -item[1],
                self._chunk_key(item[0]),
            )
        )

        return ranked_results[:top_k]

    @staticmethod
    def _rank_scores(
        results: list[tuple[DocumentChunk, float]],
    ) -> dict[str, float]:
        """Convert ranked retrieval results into normalized rank scores."""

        if not results:
            return {}

        scores: dict[str, float] = {}

        for rank, (chunk, _) in enumerate(
            results,
            start=1,
        ):
            scores[
                HybridRetriever._chunk_key(chunk)
            ] = 1.0 / rank

        return scores

    @staticmethod
    def _chunk_key(
        chunk: DocumentChunk,
    ) -> str:
        return (
            f"{chunk.source}:"
            f"{chunk.chunk_index}:"
            f"{chunk.start_line}:"
            f"{chunk.end_line}"
        )

    @staticmethod
    def _find_chunk(
        chunks: list[DocumentChunk],
        source: str,
        content: str,
    ) -> DocumentChunk | None:
        for chunk in chunks:
            if (
                chunk.source == source
                and chunk.content == content
            ):
                return chunk

        return None