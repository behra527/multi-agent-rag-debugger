import shutil
import subprocess
import tempfile
from pathlib import Path


class PatchApplier:
    """Creates an isolated repository copy and applies a unified diff."""

    def create_workspace(
        self,
        repository_path: str | Path,
    ) -> Path:
        source = Path(repository_path).resolve()

        if not source.exists():
            raise FileNotFoundError(
                f"Repository path does not exist: {source}"
            )

        if not source.is_dir():
            raise NotADirectoryError(
                f"Repository path is not a directory: {source}"
            )

        workspace = Path(
            tempfile.mkdtemp(
                prefix="debugger-workspace-"
            )
        )

        destination = workspace / source.name

        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "venv",
                "__pycache__",
                ".pytest_cache",
                "node_modules",
            ),
        )

        return destination

    def apply(
        self,
        workspace: str | Path,
        patch: str,
    ) -> None:
        if not patch.strip():
            raise ValueError("Patch must not be empty.")

        root = Path(workspace).resolve()

        if not root.exists():
            raise FileNotFoundError(
                f"Workspace does not exist: {root}"
            )

        process = subprocess.run(
            ["git", "apply", "--check", "-"],
            cwd=root,
            input=patch,
            capture_output=True,
            text=True,
            check=False,
        )

        if process.returncode != 0:
            raise ValueError(
                "Patch validation failed: "
                + process.stderr.strip()
            )

        process = subprocess.run(
            ["git", "apply", "-"],
            cwd=root,
            input=patch,
            capture_output=True,
            text=True,
            check=False,
        )

        if process.returncode != 0:
            raise ValueError(
                "Patch application failed: "
                + process.stderr.strip()
            )