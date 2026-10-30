import re
import shutil
import tempfile
from pathlib import Path

from app.core.config import settings


class SecurityViolationError(ValueError):
    """Raised when a patch or execution violates safety policies."""
    pass


class PatchSecurityValidator:
    """Validates diffs and patches against security threats."""

    # Disallowed targets
    FORBIDDEN_FILES = {
        ".env",
        ".env.example",
        "id_rsa",
        "id_ed25519",
        "passwd",
        "shadow",
        "authorized_keys",
        ".git",
    }

    FORBIDDEN_EXTENSIONS = {
        ".exe",
        ".bat",
        ".cmd",
        ".ps1",
        ".sh",
        ".dll",
        ".so",
        ".dylib",
    }

    @classmethod
    def validate_patch(cls, patch: str, workspace_root: Path) -> list[str]:
        """Validate patch paths to prevent traversal and unauthorized modifications."""
        if not patch or not patch.strip():
            raise SecurityViolationError("Patch is empty.")

        modified_files: list[str] = []

        # Find target files from git diff headers
        # e.g.: +++ b/example.py or +++ b/path/to/file.py
        for line in patch.splitlines():
            if line.startswith("+++ "):
                target = line[4:].strip()
                if target.startswith("b/"):
                    target = target[2:]
                elif target.startswith("/dev/null"):
                    continue

                # Check for path traversal attempts
                if ".." in target or target.startswith(("/", "\\")):
                    raise SecurityViolationError(
                        f"Path traversal detected in patch target: {target!r}"
                    )

                path_obj = Path(target)

                # Check forbidden file names
                if path_obj.name.lower() in cls.FORBIDDEN_FILES:
                    raise SecurityViolationError(
                        f"Modification of sensitive file is forbidden: {target!r}"
                    )

                # Check forbidden extensions
                if path_obj.suffix.lower() in cls.FORBIDDEN_EXTENSIONS:
                    raise SecurityViolationError(
                        f"Modification of executable/script files is restricted: {target!r}"
                    )

                # Verify target resolves strictly within workspace root
                resolved = (workspace_root / path_obj).resolve()
                if not str(resolved).startswith(str(workspace_root.resolve())):
                    raise SecurityViolationError(
                        f"Patch target resolves outside workspace: {target!r}"
                    )

                modified_files.append(target)

        return modified_files


class WorkspaceSandbox:
    """Disposable, isolated workspace for safe patch application and test validation."""

    def __init__(self, source_path: str | Path) -> None:
        self.source = Path(source_path).resolve()
        if not self.source.exists() or not self.source.is_dir():
            raise FileNotFoundError(f"Source repository does not exist: {self.source}")

        self.temp_dir: Path | None = None
        self.workspace_path: Path | None = None

    def __enter__(self) -> Path:
        """Create an isolated workspace clone."""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="secure-sandbox-"))
        self.workspace_path = self.temp_dir / self.source.name

        # Copy repository without sensitive or binary artifacts
        shutil.copytree(
            self.source,
            self.workspace_path,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "venv",
                "__pycache__",
                ".pytest_cache",
                "node_modules",
                "*.pyc",
                ".env*",
            ),
        )
        return self.workspace_path

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Explicitly cleanup the disposable workspace."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
