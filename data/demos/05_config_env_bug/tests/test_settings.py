import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from settings import require_app_token


def test_require_app_token_reads_app_token(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("APP_TOKEN", raising=False)
    os.environ.pop("API_TOKEN", None)
    os.environ.pop("APP_TOKEN", None)
    assert require_app_token() == "demo-local-token"
