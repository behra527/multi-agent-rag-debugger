from pathlib import Path

from app.core.grounding import (
    PatchTypeMismatch,
    assert_patch_matches_nature,
    classify_issue_nature,
)
from app.core.models import IssueRequest, ProposedFix, ValidationResult
from app.tools.patcher import PatchApplier
from app.tools.sandbox import PatchSecurityValidator, SecurityViolationError
from app.tools.validator import TestRunner


class ValidationService:
    """Applies a proposed fix in isolation and validates it."""

    def __init__(
        self,
        patcher: PatchApplier,
        test_runner: TestRunner,
    ) -> None:
        self.patcher = patcher
        self.test_runner = test_runner

    def validate(
        self,
        repository_path: str | Path,
        proposed_fix: ProposedFix,
        *,
        command: list[str] | None = None,
        issue: IssueRequest | None = None,
    ) -> ValidationResult:
        try:
            nature = classify_issue_nature(issue.title, issue.description) if issue else "code"
            workspace = self.patcher.create_workspace(
                repository_path
            )

            # Security check patch targets to prevent traversal and unauthorized modifications
            PatchSecurityValidator.validate_patch(
                proposed_fix.patch, workspace
            )
            assert_patch_matches_nature(
                proposed_fix.patch,
                proposed_fix.affected_files,
                nature=nature,
            )

            self.patcher.apply(
                workspace,
                proposed_fix.patch,
            )

            return self.test_runner.run(
                workspace,
                command=command,
            )

        except (
            FileNotFoundError,
            NotADirectoryError,
            ValueError,
            RuntimeError,
            SecurityViolationError,
            PatchTypeMismatch,
        ) as exc:
            return ValidationResult(
                passed=False,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                output="",
                errors=[str(exc)],
            )