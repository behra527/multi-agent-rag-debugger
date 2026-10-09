from pydantic import BaseModel, Field

from app.rag.loader import LoadedFile


class DocumentChunk(BaseModel):
    """A searchable chunk extracted from a repository file."""

    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    language: str
    chunk_index: int = Field(ge=0)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class RepositoryChunker:
    """Splits loaded files into line-based chunks."""

    def __init__(self, chunk_size: int = 20) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0.")

        self.chunk_size = chunk_size

    def chunk(self, files: list[LoadedFile]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []

        for file in files:
            lines = file.content.splitlines()

            if not lines:
                continue

            for start in range(0, len(lines), self.chunk_size):
                end = min(
                    start + self.chunk_size,
                    len(lines),
                )

                content = "\n".join(lines[start:end]).strip()

                if not content:
                    continue

                chunks.append(
                    DocumentChunk(
                        content=content,
                        source=file.source,
                        language=file.language,
                        chunk_index=start // self.chunk_size,
                        start_line=start + 1,
                        end_line=end,
                    )
                )

        return chunks