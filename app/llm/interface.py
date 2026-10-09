from typing import Protocol


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