from openai import OpenAI

from app.core.config import settings


class OpenRouterClient:
    """OpenRouter implementation of the LLM client."""

    def __init__(self) -> None:
        if not settings.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not configured."
            )

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError("LLM returned an empty response.")

        return content