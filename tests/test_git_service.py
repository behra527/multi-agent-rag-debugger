import subprocess
from pathlib import Path
import pytest

from app.tools.git_service import GitService, GitRepositoryInfo


def init_local_git_repo(path: Path) -> None:
    """Helper to initialize a barebones local Git repository."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test Developer"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=path, capture_output=True, check=True)


def test_is_git_repository(tmp_path):
    non_git = tmp_path / "plain_dir"
    non_git.mkdir()
    assert GitService.is_git_repository(non_git) is False

    git_repo = tmp_path / "git_dir"
    git_repo.mkdir()
    init_local_git_repo(git_repo)
    assert GitService.is_git_repository(git_repo) is True


def test_get_repository_info_and_commits(tmp_path):
    repo = tmp_path / "repo_info"
    repo.mkdir()
    init_local_git_repo(repo)

    info = GitService.get_repository_info(repo)
    assert info.is_git is True
    assert info.current_branch in {"main", "master"}
    assert info.commit_sha is not None
    assert len(info.commit_sha) == 40
    assert info.commit_author == "Test Developer"
    assert info.commit_message == "Initial commit"
    assert info.is_clean is True

    # Test listing commits
    commits = GitService.list_recent_commits(repo, limit=5)
    assert len(commits) == 1
    assert commits[0].sha == info.commit_sha
    assert commits[0].message == "Initial commit"


def test_create_fix_branch(tmp_path):
    repo = tmp_path / "repo_branch"
    repo.mkdir()
    init_local_git_repo(repo)

    # Valid branch
    res = GitService.create_fix_branch(repo, "fix/issue-101")
    assert res["created"] is True
    assert res["branch"] == "fix/issue-101"

    info = GitService.get_repository_info(repo)
    assert info.current_branch == "fix/issue-101"

    # Reject invalid / path traversal branch names
    with pytest.raises(ValueError, match="Invalid branch name"):
        GitService.create_fix_branch(repo, "../escape")

    with pytest.raises(ValueError, match="Invalid branch name"):
        GitService.create_fix_branch(repo, "-flag")


def test_commit_approved_patch(tmp_path):
    repo = tmp_path / "repo_patch"
    repo.mkdir()
    init_local_git_repo(repo)

    (repo / "math_lib.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    subprocess.run(["git", "add", "math_lib.py"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Add buggy math_lib"], cwd=repo, capture_output=True, check=True)

    patch = (
        "diff --git a/math_lib.py b/math_lib.py\n"
        "--- a/math_lib.py\n"
        "+++ b/math_lib.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def add(a, b):\n"
        "-    return a - b\n"
        "+    return a + b\n"
    )

    res = GitService.commit_approved_patch(
        repo_path=repo,
        patch=patch,
        commit_message="Fix addition operator in math_lib",
        branch_name="fix/add-operator",
        author_name="AI Debugger Agent",
        author_email="agent@debugger.ai",
    )

    assert res["commit_sha"] is not None
    assert len(res["commit_sha"]) == 40
    assert "math_lib.py" in res["modified_files"]
    assert res["branch"] == "fix/add-operator"

    # Verify file content
    assert (repo / "math_lib.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"


def test_clone_security_rejects_ssrf_and_file_schemes(tmp_path):
    target = tmp_path / "cloned"

    # Reject file://
    with pytest.raises(ValueError, match="Unsupported or dangerous URL scheme"):
        GitService.clone_repository("file:///etc/passwd", target)

    # Reject localhost SSRF
    with pytest.raises(ValueError, match="loopback"):
        GitService.clone_repository("https://localhost:8080/repo.git", target)

    with pytest.raises(ValueError, match="loopback"):
        GitService.clone_repository("https://127.0.0.1/evil.git", target)


def test_detect_project_tooling(tmp_path):
    py_repo = tmp_path / "py_project"
    py_repo.mkdir()
    (py_repo / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    lang, cmd = GitService.detect_project_tooling(py_repo)
    assert lang == "Python"
    assert cmd == ["pytest", "-q"]

    js_repo = tmp_path / "js_project"
    js_repo.mkdir()
    (js_repo / "package.json").write_text('{"name": "test", "scripts": {"test": "jest"}}', encoding="utf-8")
    lang_js, cmd_js = GitService.detect_project_tooling(js_repo)
    assert lang_js == "JavaScript / TypeScript"
    assert cmd_js == ["npm", "test"]
