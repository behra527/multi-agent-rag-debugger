import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_run_greets_the_name():
    from app import run

    assert run("Ada") == "Hello, Ada"
