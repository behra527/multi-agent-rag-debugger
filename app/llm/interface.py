from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class GenerationResult:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model: str | None = None
    retries: int = 0
    raw: dict = field(default_factory=dict)


class LLMClient(Protocol):
    """Interface that every LLM provider must implement."""

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a text response from the LLM."""
        ...

    def generate_result(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> GenerationResult:
        ...
