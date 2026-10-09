import re

from app.rag.chunker import DocumentChunk


class KeywordRetriever:
    """Retrieves repository chunks using keyword matching."""

    def retrieve(
        self,
        query: str,
        chunks: list[DocumentChunk],
        *,
        top_k: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        if not query.strip():
            raise ValueError("query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0.")

        query_terms = self._tokenize(query)

        if not query_terms:
            return []

        scored_chunks: list[
            tuple[DocumentChunk, float]
        ] = []

        for chunk in chunks:
            chunk_terms = self._tokenize(chunk.content)

            if not chunk_terms:
                continue

            matches = sum(
                1
                for term in query_terms
                if term in chunk_terms
            )

            if matches == 0:
                continue

            score = matches / len(query_terms)

            scored_chunks.append(
                (chunk, score)
            )

        scored_chunks.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        return scored_chunks[:top_k]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Convert text into normalized searchable terms."""

        return set(
            re.findall(
                r"\b[a-zA-Z_][a-zA-Z0-9_]*\b",
                text.lower(),
            )
        )