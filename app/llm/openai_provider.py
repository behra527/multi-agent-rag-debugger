from openai import OpenAI

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.llm.interface import GenerationResult
from app.llm.runtime import chat_complete


class OpenAIClient:
    """Direct OpenAI API implementation of LLMClient."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or settings.openai_api_key
        if not key:
            raise ConfigurationError("OPENAI_API_KEY is not configured.")

        self.model = model or settings.openai_model
        self.client = OpenAI(
            api_key=key,
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
            provider_name="OpenAI",
        )

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        return self.generate_result(prompt, system_prompt=system_prompt).text
