
from pathlib import Path

from app.core.models import ProposedFix, ValidationResult
from app.tools.patcher import PatchApplier
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
    ) -> ValidationResult:
        try:
            workspace = self.patcher.create_workspace(
                repository_path
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
        ) as exc:
            return ValidationResult(
                passed=False,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                output="",
                errors=[str(exc)],
            )