from openai import OpenAI

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.llm.interface import GenerationResult
from app.llm.runtime import chat_complete


class OpenRouterClient:
    """OpenRouter implementation of the LLM client."""

    def __init__(self) -> None:
        if not settings.openrouter_api_key:
            raise ConfigurationError("OPENROUTER_API_KEY is not configured.")

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        self.model = settings.llm_model

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
            provider_name="OpenRouter",
        )

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        return self.generate_result(prompt, system_prompt=system_prompt).text
