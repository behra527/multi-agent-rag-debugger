from pathlib import Path

from pydantic import BaseModel, Field


LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".md": "markdown",
    ".txt": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}


class LoadedFile(BaseModel):
    """A loaded repository file with useful metadata."""

    source: str = Field(min_length=1)
    content: str
    extension: str
    language: str
    size: int = Field(ge=0)


class RepositoryLoader:
    """Loads discovered repository files into structured objects."""

    def load(self, files: list[Path]) -> list[LoadedFile]:
        loaded_files: list[LoadedFile] = []

        for file_path in files:
            content = file_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )

            extension = file_path.suffix.lower()

            loaded_files.append(
                LoadedFile(
                    source=str(file_path),
                    content=content,
                    extension=extension,
                    language=LANGUAGE_MAP.get(
                        extension,
                        "unknown",
                    ),
                    size=file_path.stat().st_size,
                )
            )

        return loaded_files