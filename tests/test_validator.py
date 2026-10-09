from app.tools.validator import TestRunner


def test_runner_executes_successful_command(tmp_path):
    runner = TestRunner()

    result = runner.run(
        tmp_path,
        command=["python", "-c", "print('tests passed')"],
    )

    assert result.passed is True
    assert result.output.strip() == "tests passed"
    assert result.errors == []


def test_runner_handles_failed_command(tmp_path):
    runner = TestRunner()

    result = runner.run(
        tmp_path,
        command=[
            "python",
            "-c",
            "import sys; sys.exit(1)",
        ],
    )

    assert result.passed is False
    assert result.tests_run == 0
    assert result.tests_passed == 0
    assert result.tests_failed == 0
    assert len(result.errors) == 1


def test_runner_rejects_missing_repository(tmp_path):
    runner = TestRunner()

    missing_path = tmp_path / "missing"

    try:
        runner.run(missing_path)
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_runner_executes_real_pytest_suite(tmp_path):
    test_file = tmp_path / "test_sample.py"

    test_file.write_text(
        """
def test_sample():
    assert 1 + 1 == 2
""",
        encoding="utf-8",
    )

    runner = TestRunner()

    result = runner.run(
        tmp_path,
        command=["pytest", "-q"],
    )

    assert result.passed is True
    assert result.tests_run > 0
    assert result.tests_passed > 0
    assert result.tests_failed == 0