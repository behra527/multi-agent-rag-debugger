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
    symbols: list[str] = Field(default_factory=list)


class RepositoryChunker:
    """Splits loaded files into line-based chunks with optional AST symbol awareness."""

    def __init__(self, chunk_size: int = 20, enable_ast: bool = True) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0.")

        self.chunk_size = chunk_size
        self.enable_ast = enable_ast
        self._ast_parser = None
        if enable_ast:
            from app.rag.ast_parser import PythonASTParser
            self._ast_parser = PythonASTParser()


    def chunk(self, files: list[LoadedFile]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []

        for file in files:
            lines = file.content.splitlines()
            if not lines:
                continue

            file_symbols = []
            if self._ast_parser and file.language == "python":
                file_symbols = self._ast_parser.extract_symbols(file.content)

            for start in range(0, len(lines), self.chunk_size):
                end = min(
                    start + self.chunk_size,
                    len(lines),
                )

                content = "\n".join(lines[start:end]).strip()

                if not content:
                    continue

                start_line = start + 1
                end_line = end
                chunk_symbols = [
                    s.name
                    for s in file_symbols
                    if not (s.end_line < start_line or s.start_line > end_line)
                ]

                chunks.append(
                    DocumentChunk(
                        content=content,
                        source=file.source,
                        language=file.language,
                        chunk_index=start // self.chunk_size,
                        start_line=start_line,
                        end_line=end_line,
                        symbols=chunk_symbols,
                    )
                )

        return chunks