from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.llm.interface import LLMClient
from app.llm.mock_provider import MockLLMClient
from app.llm.ollama_provider import OllamaClient
from app.llm.openai_provider import OpenAIClient
from app.llm.openrouter import OpenRouterClient


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Instantiate the configured LLM provider client.

    Missing credentials fail loudly. Mock is used only when explicitly selected.
    """
    selected = (provider or settings.llm_provider).lower().strip()

    if selected == "openai":
        return OpenAIClient()
    if selected == "ollama":
        return OllamaClient()
    if selected == "mock":
        return MockLLMClient()
    if selected == "openrouter":
        return OpenRouterClient()

    raise ConfigurationError(
        f"Unknown LLM provider '{selected}'. Use openai, openrouter, ollama, or mock."
    )
