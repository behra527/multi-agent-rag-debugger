from app.rag.loader import RepositoryLoader
from app.rag.scanner import RepositoryScanner


def test_loader_reads_file_content():
    scanner = RepositoryScanner()
    loader = RepositoryLoader()

    files = scanner.scan("data/sample_project")
    loaded_files = loader.load(files)

    login_file = next(
        file for file in loaded_files
        if file.extension == ".py"
    )

    assert "def login" in login_file.content
    assert login_file.language == "python"


def test_loader_extracts_metadata():
    scanner = RepositoryScanner()
    loader = RepositoryLoader()

    files = scanner.scan("data/sample_project")
    loaded_files = loader.load(files)

    config_file = next(
        file for file in loaded_files
        if file.extension == ".json"
    )

    assert config_file.extension == ".json"
    assert config_file.language == "json"
    assert config_file.size >= 0


def test_loader_loads_all_supported_files():
    scanner = RepositoryScanner()
    loader = RepositoryLoader()

    files = scanner.scan("data/sample_project")
    loaded_files = loader.load(files)

    assert len(loaded_files) == 3