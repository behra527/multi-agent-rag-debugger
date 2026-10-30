from openai import OpenAI

from app.core.config import settings
from app.core.security import assert_safe_provider_url
from app.llm.interface import GenerationResult
from app.llm.runtime import chat_complete


class OllamaClient:
    """Ollama local model implementation using its OpenAI-compatible endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        assert_safe_provider_url(self.base_url)
        self.model = model or settings.ollama_model
        self.client = OpenAI(
            base_url=self.base_url,
            api_key="ollama",
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def generate_result(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> GenerationResult:
        return chat_complete(
            self.client,
            model=self.model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            provider_name="Ollama",
        )

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        return self.generate_result(prompt, system_prompt=system_prompt).text
