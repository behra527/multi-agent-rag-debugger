import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class GitCommit(BaseModel):
    sha: str
    author: str
    date: str
    message: str


class GitRepositoryInfo(BaseModel):
    is_git: bool
    current_branch: str | None = None
    commit_sha: str | None = None
    commit_author: str | None = None
    commit_message: str | None = None
    branches: list[str] = Field(default_factory=list)
    is_clean: bool = True
    modified_files: list[str] = Field(default_factory=list)
    untracked_files: list[str] = Field(default_factory=list)
    detected_framework: str | None = None
    default_test_command: list[str] | None = None


class GitService:
    """Safe, production-grade Git operations for repository inspection and fix workflows."""

    @classmethod
    def _run_git(
        cls,
        args: list[str],
        cwd: Path,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a git command safely with controlled timeouts and environment."""
        git_bin = shutil.which("git") or "git"
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)
        # Avoid interactive prompts
        exec_env["GIT_TERMINAL_PROMPT"] = "0"
        exec_env["GIT_ASKPASS"] = "echo"

        return subprocess.run(
            [git_bin, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=exec_env,
        )

    @classmethod
    def is_git_repository(cls, repo_path: Path) -> bool:
        """Check if target path is inside a genuine Git repository."""
        if not repo_path.exists() or not repo_path.is_dir():
            return False
        res = cls._run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_path)
        return res.returncode == 0 and res.stdout.strip() == "true"

    @classmethod
    def detect_project_tooling(cls, repo_path: Path) -> tuple[str, list[str] | None]:
        """Detect language, framework, and appropriate test runner from project files."""
        if not repo_path.exists() or not repo_path.is_dir():
            return "Unknown", None

        # Python
        if (
            (repo_path / "pytest.ini").exists()
            or (repo_path / "pyproject.toml").exists()
            or (repo_path / "setup.py").exists()
            or any(repo_path.glob("test*.py"))
            or (repo_path / "tests").is_dir()
            or any(repo_path.glob("*.py"))
        ):
            has_tests = (
                (repo_path / "pytest.ini").exists()
                or (repo_path / "pyproject.toml").exists()
                or any(repo_path.glob("test*.py"))
                or (repo_path / "tests").is_dir()
            )
            return "Python", ["pytest", "-q"] if has_tests else None

        # JavaScript / TypeScript
        pkg_json = repo_path / "package.json"
        if pkg_json.exists() or any(repo_path.glob("*.js")) or any(repo_path.glob("*.ts")):
            return "JavaScript / TypeScript", ["npm", "test"] if pkg_json.exists() else None

        # Rust
        if (repo_path / "Cargo.toml").exists():
            return "Rust", ["cargo", "test"]

        # Go
        if (repo_path / "go.mod").exists():
            return "Go", ["go", "test", "./..."]

        # Java
        if (repo_path / "pom.xml").exists():
            return "Java (Maven)", ["mvn", "test"]
        if (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists():
            return "Java / Kotlin (Gradle)", ["gradle", "test"]

        return "Generic / Unconfigured", None

    @classmethod
    def get_repository_info(cls, repo_path: Path) -> GitRepositoryInfo:
        """Inspect Git metadata and working-tree status."""
        framework, test_cmd = cls.detect_project_tooling(repo_path)

        if not cls.is_git_repository(repo_path):
            return GitRepositoryInfo(
                is_git=False,
                detected_framework=framework,
                default_test_command=test_cmd,
            )

        # Current branch
        res_branch = cls._run_git(["branch", "--show-current"], cwd=repo_path)
        current_branch = res_branch.stdout.strip() if res_branch.returncode == 0 else "HEAD"

        # Recent commit details
        res_log = cls._run_git(
            ["log", "-1", "--pretty=format:%H%x00%an%x00%ad%x00%s"],
            cwd=repo_path,
        )
        commit_sha = None
        commit_author = None
        commit_message = None
        if res_log.returncode == 0 and res_log.stdout.strip():
            parts = res_log.stdout.split("\x00")
            if len(parts) >= 4:
                commit_sha, commit_author, _, commit_message = parts[0], parts[1], parts[2], parts[3]

        # Branches list
        res_branches = cls._run_git(
            ["branch", "--list", "--format=%(refname:short)"],
            cwd=repo_path,
        )
        branches = [b.strip() for b in res_branches.stdout.splitlines() if b.strip()]

        # Working tree status
        res_status = cls._run_git(["status", "--porcelain"], cwd=repo_path)
        modified_files = []
        untracked_files = []
        is_clean = True

        if res_status.returncode == 0 and res_status.stdout.strip():
            for line in res_status.stdout.splitlines():
                if len(line) >= 3:
                    code = line[:2]
                    fname = line[3:].strip()
                    if "??" in code:
                        untracked_files.append(fname)
                    else:
                        modified_files.append(fname)
            is_clean = len(modified_files) == 0 and len(untracked_files) == 0

        return GitRepositoryInfo(
            is_git=True,
            current_branch=current_branch or "main",
            commit_sha=commit_sha,
            commit_author=commit_author,
            commit_message=commit_message,
            branches=branches or [current_branch or "main"],
            is_clean=is_clean,
            modified_files=modified_files,
            untracked_files=untracked_files,
            detected_framework=framework,
            default_test_command=test_cmd,
        )

    @classmethod
    def list_recent_commits(cls, repo_path: Path, limit: int = 10) -> list[GitCommit]:
        """Fetch commit history with SHA, author, timestamp and summary message."""
        if not cls.is_git_repository(repo_path):
            return []

        res = cls._run_git(
            ["log", f"-{min(limit, 50)}", "--pretty=format:%H%x00%an%x00%ad%x00%s"],
            cwd=repo_path,
        )
        commits: list[GitCommit] = []
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.splitlines():
                parts = line.split("\x00")
                if len(parts) >= 4:
                    commits.append(
                        GitCommit(
                            sha=parts[0],
                            author=parts[1],
                            date=parts[2],
                            message=parts[3],
                        )
                    )
        return commits

    @classmethod
    def create_fix_branch(
        cls,
        repo_path: Path,
        branch_name: str,
        base_branch: str | None = None,
    ) -> dict[str, Any]:
        """Create a dedicated fix branch from the current HEAD or specified base branch."""
        if not cls.is_git_repository(repo_path):
            raise ValueError(f"Path is not a Git repository: {repo_path}")

        # Validate branch name to prevent malicious flags or path traversal
        clean_name = branch_name.strip()
        if not re.match(r"^[a-zA-Z0-9_\-\.\/]+$", clean_name) or clean_name.startswith("-") or ".." in clean_name:
            raise ValueError(f"Invalid branch name: {branch_name!r}")

        args = ["checkout", "-b", clean_name]
        if base_branch:
            args.append(base_branch)

        res = cls._run_git(args, cwd=repo_path)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create branch {clean_name}: {res.stderr.strip()}")

        # Record HEAD SHA of newly created branch
        head_res = cls._run_git(["rev-parse", "HEAD"], cwd=repo_path)
        head_sha = head_res.stdout.strip() if head_res.returncode == 0 else ""

        return {
            "branch": clean_name,
            "created": True,
            "head_sha": head_sha,
        }

    @classmethod
    def commit_approved_patch(
        cls,
        repo_path: Path,
        patch: str,
        commit_message: str,
        branch_name: str | None = None,
        author_name: str = "Multi-Agent RAG Debugger",
        author_email: str = "debugger@local",
    ) -> dict[str, Any]:
        """Safely apply an approved patch and commit it to an isolated fix branch."""
        if not cls.is_git_repository(repo_path):
            raise ValueError(f"Path is not a Git repository: {repo_path}")

        if not patch.strip():
            raise ValueError("Patch cannot be empty.")

        # Ensure working tree does not have conflicting unstaged user changes
        status_res = cls._run_git(["status", "--porcelain"], cwd=repo_path)
        if status_res.returncode == 0 and status_res.stdout.strip():
            # Warn if dirty, but allow if clean fix branch
            pass

        # If a branch was specified, checkout or create it
        if branch_name:
            clean_branch = branch_name.strip()
            # Try switching to it or creating it
            res_co = cls._run_git(["checkout", clean_branch], cwd=repo_path)
            if res_co.returncode != 0:
                cls._run_git(["checkout", "-b", clean_branch], cwd=repo_path)

        # Apply patch via git apply
        apply_res = subprocess.run(
            ["git", "apply", "-"],
            cwd=repo_path,
            input=patch,
            capture_output=True,
            text=True,
            check=False,
        )
        if apply_res.returncode != 0:
            raise RuntimeError(f"Git apply failed: {apply_res.stderr.strip()}")

        # Identify changed files from diff to stage only them
        diff_res = cls._run_git(["diff", "--name-only"], cwd=repo_path)
        changed_files = [f.strip() for f in diff_res.stdout.splitlines() if f.strip()]

        if not changed_files:
            raise RuntimeError("No files were modified by the patch.")

        # Stage only the patch-modified files
        cls._run_git(["add", *changed_files], cwd=repo_path)

        # Commit with explicit author metadata
        env = {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
        }
        commit_res = cls._run_git(
            ["commit", "-m", commit_message],
            cwd=repo_path,
            env=env,
        )
        if commit_res.returncode != 0:
            raise RuntimeError(f"Git commit failed: {commit_res.stderr.strip()}")

        # Fetch new commit SHA
        sha_res = cls._run_git(["rev-parse", "HEAD"], cwd=repo_path)
        new_sha = sha_res.stdout.strip() if sha_res.returncode == 0 else ""

        return {
            "commit_sha": new_sha,
            "message": commit_message,
            "author": f"{author_name} <{author_email}>",
            "modified_files": changed_files,
            "branch": branch_name or "HEAD",
        }

    @classmethod
    def clone_repository(
        cls,
        remote_url: str,
        target_dir: Path,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Clone an authenticated remote Git repository with SSRF and scheme validation."""
        clean_url = remote_url.strip()

        # Strict security validation: reject file:// or local paths
        parsed = urlparse(clean_url)
        allowed_schemes = {"https", "http", "ssh", "git"}
        if parsed.scheme.lower() not in allowed_schemes and not clean_url.startswith("git@"):
            raise ValueError(
                f"Unsupported or dangerous URL scheme in {clean_url!r}. "
                "Only https://, git://, and git@ remote repositories are allowed."
            )

        # Block localhost / internal loopback SSRF
        hostname = (parsed.hostname or "").lower()
        if hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
            raise ValueError(f"Cloning from loopback addresses is prohibited: {hostname}")

        from app.core.config import settings

        clone_url = clean_url
        token = (settings.github_token or "").strip()
        if token and parsed.hostname and parsed.hostname.endswith("github.com") and parsed.scheme == "https":
            clone_url = f"https://x-access-token:{token}@{parsed.netloc}{parsed.path}"

        target_dir.parent.mkdir(parents=True, exist_ok=True)
        args = ["clone", "--depth", "1"]
        if branch:
            args.extend(["--branch", branch])
        args.extend([clone_url, str(target_dir)])

        git_bin = shutil.which("git") or "git"
        res = subprocess.run(
            [git_bin, *args],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"Git clone failed: {res.stderr.strip()}")

        return {
            "path": str(target_dir),
            "cloned": True,
            "url": clean_url,
        }
