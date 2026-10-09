from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
}


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
}


class RepositoryScanner:
    """Discovers supported files inside a repository."""

    def scan(self, repository_path: str | Path) -> list[Path]:
        root = Path(repository_path).resolve()

        if not root.exists():
            raise FileNotFoundError(
                f"Repository path does not exist: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Repository path is not a directory: {root}"
            )

        files: list[Path] = []

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if any(
                ignored in path.parts
                for ignored in IGNORED_DIRECTORIES
            ):
                continue

            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            files.append(path)

        return sorted(files)