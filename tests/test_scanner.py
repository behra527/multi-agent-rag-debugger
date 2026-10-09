
from app.rag.scanner import RepositoryScanner


def test_scanner_finds_supported_files():
    scanner = RepositoryScanner()

    files = scanner.scan("data/sample_project")

    names = {file.name for file in files}

    assert "login.py" in names
    assert "README.md" in names
    assert "config.json" in names
    assert "ignored.exe" not in names


def test_scanner_returns_sorted_paths():
    scanner = RepositoryScanner()

    files = scanner.scan("data/sample_project")

    assert files == sorted(files)


def test_scanner_rejects_missing_repository():
    scanner = RepositoryScanner()

    try:
        scanner.scan("data/does_not_exist")
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass

