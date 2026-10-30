import pytest

from app.core.models import ProposedFix
from app.tools.patcher import PatchApplier
from app.tools.sandbox import PatchSecurityValidator, SecurityViolationError, WorkspaceSandbox
from app.tools.validation_service import ValidationService
from app.tools.validator import TestRunner


def test_sandbox_creates_and_cleans_up(tmp_path):
    repo = tmp_path / "sample_repo"
    repo.mkdir()
    (repo / "hello.py").write_text("print('hello')", encoding="utf-8")

    workspace_created = None
    with WorkspaceSandbox(repo) as ws:
        assert ws.exists()
        assert (ws / "hello.py").exists()
        workspace_created = ws.parent

    # Check cleanup
    assert not workspace_created.exists()


def test_patch_security_validator_blocks_path_traversal(tmp_path):
    patch = (
        "diff --git a/safe.py b/../../etc/passwd\n"
        "--- a/safe.py\n"
        "+++ b/../../etc/passwd\n"
        "@@ -1 +1 @@\n"
        "-root:x:0:0\n"
        "+root:x:0:0:hacked\n"
    )

    with pytest.raises(SecurityViolationError, match="Path traversal detected"):
        PatchSecurityValidator.validate_patch(patch, tmp_path)


def test_patch_security_validator_blocks_sensitive_files(tmp_path):
    patch = (
        "diff --git a/.env b/.env\n"
        "--- a/.env\n"
        "+++ b/.env\n"
        "@@ -1 +1 @@\n"
        "-SECRET=1\n"
        "+SECRET=2\n"
    )

    with pytest.raises(SecurityViolationError, match="Modification of sensitive file is forbidden"):
        PatchSecurityValidator.validate_patch(patch, tmp_path)


def test_patch_security_validator_blocks_executable_scripts(tmp_path):
    patch = (
        "diff --git a/run.sh b/run.sh\n"
        "--- a/run.sh\n"
        "+++ b/run.sh\n"
        "@@ -1 +1 @@\n"
        "-echo 1\n"
        "+rm -rf /\n"
    )

    with pytest.raises(SecurityViolationError, match="Modification of executable/script files is restricted"):
        PatchSecurityValidator.validate_patch(patch, tmp_path)


def test_validation_service_rejects_malicious_patch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print(1)", encoding="utf-8")

    fix = ProposedFix(
        summary="Malicious fix",
        affected_files=["../../etc/passwd"],
        patch="diff --git a/app.py b/../../etc/passwd\n--- a/app.py\n+++ b/../../etc/passwd\n",
        reasoning="Exploit attempt",
    )

    service = ValidationService(
        patcher=PatchApplier(),
        test_runner=TestRunner(),
    )

    result = service.validate(repo, fix)
    assert result.passed is False
    assert len(result.errors) >= 1
    assert "Path traversal detected" in result.errors[0]
