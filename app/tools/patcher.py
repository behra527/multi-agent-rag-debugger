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

    @staticmethod
    def verify_patch_targets(workspace: Path, patch: str) -> list[str]:
        """Return a list of targeted file paths; raise ValueError if any are missing.

        Only checks files that are being modified (not new files being created,
        which appear as /dev/null in the --- line).
        """
        missing: list[str] = []
        target_files: list[str] = []

        lines = patch.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("--- "):
                src = line[4:].strip()
                # Skip new files (diff creates them, they won't exist yet)
                if src in {"/dev/null", ""}:
                    continue
                if src.startswith("a/"):
                    src = src[2:]
                target_files.append(src)

        for src in target_files:
            candidate = (workspace / src).resolve()
            # Ensure it's within workspace (basic containment check)
            try:
                candidate.relative_to(workspace.resolve())
            except ValueError:
                raise ValueError(
                    f"Patch target '{src}' resolves outside workspace. "
                    "This may be a path traversal attempt."
                )
            if not candidate.exists():
                missing.append(src)

        if missing:
            raise ValueError(
                f"Patch references file(s) that do not exist in the target "
                f"repository workspace: {', '.join(missing)}. "
                f"Ensure the patch was generated for this repository and revision."
            )

        return target_files

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

        # Verify that all modified files exist before applying.
        self.verify_patch_targets(root, patch)

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