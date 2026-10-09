
from app.core.models import ProposedFix
from app.tools.patcher import PatchApplier
from app.tools.validation_service import ValidationService
from app.tools.validator import TestRunner


def test_validation_service_validates_patched_repository(tmp_path):
    repository = tmp_path / "project"
    repository.mkdir()

    source_file = repository / "example.py"
    source_file.write_text(
        "def calculate():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    test_file = repository / "test_example.py"
    test_file.write_text(
        "from example import calculate\n\n"
        "def test_calculate():\n"
        "    assert calculate() == 2\n",
        encoding="utf-8",
    )

    patch = (
        "diff --git a/example.py b/example.py\n"
        "index 1234567..abcdefg 100644\n"
        "--- a/example.py\n"
        "+++ b/example.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def calculate():\n"
        "-    return 1\n"
        "+    return 2\n"
    )

    proposed_fix = ProposedFix(
        summary="Correct the calculation result.",
        affected_files=["example.py"],
        patch=patch,
        reasoning="The function returns the wrong value.",
    )

    service = ValidationService(
        patcher=PatchApplier(),
        test_runner=TestRunner(),
    )

    result = service.validate(
        repository,
        proposed_fix,
        command=["pytest", "-q"],
    )

    assert result.passed is True
    assert result.tests_run == 1
    assert result.tests_passed == 1
    assert result.tests_failed == 0

    assert source_file.read_text(
        encoding="utf-8"
    ) == (
        "def calculate():\n"
        "    return 1\n"
    )


def test_validation_service_rejects_invalid_patch(tmp_path):
    repository = tmp_path / "project"
    repository.mkdir()

    source_file = repository / "example.py"
    source_file.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    patch = (
        "diff --git a/example.py b/example.py\n"
        "index 1234567..abcdefg 100644\n"
        "--- a/example.py\n"
        "+++ b/example.py\n"
        "@@ -1 +1 @@\n"
        "-value = 999\n"
        "+value = 2\n"
    )

    proposed_fix = ProposedFix(
        summary="Invalid patch.",
        affected_files=["example.py"],
        patch=patch,
        reasoning="Test invalid patch handling.",
    )

    service = ValidationService(
        patcher=PatchApplier(),
        test_runner=TestRunner(),
    )

    result = service.validate(
        repository,
        proposed_fix,
    )

    assert result.passed is False
    assert result.tests_run == 0
    assert len(result.errors) == 1
    assert "Patch validation failed" in result.errors[0]


def test_validation_service_handles_missing_repository(tmp_path):
    missing_repository = tmp_path / "missing-project"

    proposed_fix = ProposedFix(
        summary="Test missing repository handling.",
        affected_files=["example.py"],
        patch="diff --git a/example.py b/example.py\n",
        reasoning="Verify the service handles a missing repository.",
    )

    service = ValidationService(
        patcher=PatchApplier(),
        test_runner=TestRunner(),
    )

    result = service.validate(
        missing_repository,
        proposed_fix,
    )

    assert result.passed is False
    assert result.tests_run == 0
    assert result.tests_passed == 0
    assert result.tests_failed == 0
    assert len(result.errors) == 1
    assert "Repository path does not exist" in result.errors[0]


def test_validation_service_handles_test_runner_exception(tmp_path):
    repository = tmp_path / "project"
    repository.mkdir()

    source_file = repository / "example.py"
    source_file.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    patch = (
        "diff --git a/example.py b/example.py\n"
        "index 1234567..abcdefg 100644\n"
        "--- a/example.py\n"
        "+++ b/example.py\n"
        "@@ -1 +1 @@\n"
        "-value = 1\n"
        "+value = 2\n"
    )

    proposed_fix = ProposedFix(
        summary="Test unexpected runner failure.",
        affected_files=["example.py"],
        patch=patch,
        reasoning="Verify unexpected test runner errors.",
    )

    class FailingTestRunner:
        def run(self, repository_path, *, command=None):
            raise RuntimeError("Unexpected test runner failure.")

    service = ValidationService(
        patcher=PatchApplier(),
        test_runner=FailingTestRunner(),
    )

    result = service.validate(
        repository,
        proposed_fix,
    )

    assert result.passed is False
    assert result.tests_run == 0
    assert result.tests_passed == 0
    assert result.tests_failed == 0
    assert "Unexpected test runner failure." in result.errors[0]