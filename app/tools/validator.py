import subprocess
from pathlib import Path

from app.core.models import ValidationResult


class TestRunner:
    """Runs a project's test suite and returns a structured result."""

    def run(
        self,
        repository_path: str | Path,
        *,
        command: list[str] | None = None,
    ) -> ValidationResult:
        root = Path(repository_path).resolve()

        if not root.exists():
            raise FileNotFoundError(
                f"Repository path does not exist: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Repository path is not a directory: {root}"
            )

        test_command = command or ["pytest", "-q"]

        try:
            process = subprocess.run(
                test_command,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ValidationResult(
                passed=False,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                output=str(exc),
                errors=["Test execution timed out after 120 seconds."],
            )
        except OSError as exc:
            return ValidationResult(
                passed=False,
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                output="",
                errors=[str(exc)],
            )

        output = "\n".join(
            part
            for part in (
                process.stdout,
                process.stderr,
            )
            if part
        )

        passed = process.returncode == 0

        return ValidationResult(
            passed=passed,
            tests_run=self._parse_tests_run(output),
            tests_passed=self._parse_tests_passed(output),
            tests_failed=self._parse_tests_failed(output),
            output=output,
            errors=[] if passed else [
                "Test suite exited with a non-zero status."
            ],
        )

    @staticmethod
    def _parse_tests_run(output: str) -> int:
        """Extract total test count from common pytest output."""

        for line in reversed(output.splitlines()):
            if "passed" in line or "failed" in line:
                parts = line.split()

                for index, part in enumerate(parts):
                    if part in {"passed", "failed"} and index > 0:
                        try:
                            return int(parts[index - 1])
                        except ValueError:
                            continue

        return 0

    @staticmethod
    def _parse_tests_passed(output: str) -> int:
        """Extract passed test count from pytest output."""

        for line in reversed(output.splitlines()):
            if "passed" not in line:
                continue

            parts = line.split()

            for index, part in enumerate(parts):
                if part == "passed" and index > 0:
                    try:
                        return int(parts[index - 1])
                    except ValueError:
                        continue

        return 0

    @staticmethod
    def _parse_tests_failed(output: str) -> int:
        """Extract failed test count from pytest output."""

        for line in reversed(output.splitlines()):
            if "failed" not in line:
                continue

            parts = line.split()

            for index, part in enumerate(parts):
                if part == "failed" and index > 0:
                    try:
                        return int(parts[index - 1])
                    except ValueError:
                        continue

        return 0