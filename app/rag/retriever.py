
from app.core.models import (
    Evidence,
    RetrievedDocument,
    RetrievalResult,
)
from app.rag.embeddings import EmbeddingProvider
from app.rag.vector_store import VectorStore


class RepositoryRetriever:
    """Retrieves relevant repository evidence using vector similarity."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> RetrievalResult:
        if not query.strip():
            raise ValueError("query must not be empty.")

        query_embedding = self.embedding_provider.embed([query])[0]

        results = self.vector_store.search(
            query_embedding,
            top_k=top_k,
        )

        documents = [
            RetrievedDocument(
                source=chunk.source,
                content=chunk.content,
                score=score,
                metadata={
                    "language": chunk.language,
                    "chunk_index": str(chunk.chunk_index),
                    "start_line": str(chunk.start_line),
                    "end_line": str(chunk.end_line),
                },
            )
            for chunk, score in results
        ]

        return RetrievalResult(
            documents=documents,
            query=query,
        )

    def to_evidence(
        self,
        result: RetrievalResult,
    ) -> list[Evidence]:
        """Convert retrieved documents into agent-ready evidence."""

        evidence: list[Evidence] = []

        for document in result.documents:
            evidence.append(
                Evidence(
                    source=document.source,
                    content=document.content,
                    score=document.score,
                    start_line=int(
                        document.metadata["start_line"]
                    ),
                    end_line=int(
                        document.metadata["end_line"]
                    ),
                    language=document.metadata["language"],
                )
            )

        return evidence

