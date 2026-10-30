from __future__ import annotations

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from app.core.exceptions import ProviderError
from app.llm.interface import GenerationResult


def chat_complete(
    client: OpenAI,
    *,
    model: str,
    prompt: str,
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
    provider_name: str,
) -> GenerationResult:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except RateLimitError as exc:
        raise ProviderError(
            f"{provider_name} rate-limited the request.",
            details={"model": model},
        ) from exc
    except (APITimeoutError, APIConnectionError) as exc:
        raise ProviderError(
            f"{provider_name} request failed due to timeout or connectivity.",
            details={"model": model},
        ) from exc
    except APIStatusError as exc:
        if exc.status_code and 400 <= exc.status_code < 500 and exc.status_code != 429:
            raise ProviderError(
                f"{provider_name} rejected the request ({exc.status_code}).",
                details={"model": model, "status": exc.status_code},
            ) from exc
        raise ProviderError(
            f"{provider_name} returned an error.",
            details={"model": model},
        ) from exc
    except Exception as exc:
        raise ProviderError(
            f"{provider_name} call failed: {exc}",
            details={"model": model},
        ) from exc

    if not response.choices:
        raise ProviderError(f"{provider_name} returned no choices.", details={"model": model})

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ProviderError(f"{provider_name} returned empty content.", details={"model": model})

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

    return GenerationResult(
        text=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=model,
    )
