
import pytest

from app.core.config import settings
from app.llm.openrouter import OpenRouterClient


def test_openrouter_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    with pytest.raises(
        ValueError,
        match="OPENROUTER_API_KEY",
    ):
        OpenRouterClient()
