"""Usage, latency, and estimated-cost tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from app.core.config import settings


@dataclass
class UsageStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0
    embedding_calls: int = 0
    retries: int = 0
    estimated_cost_usd: float = 0.0
    latencies_ms: dict[str, float] = field(default_factory=dict)

    def add_llm_tokens(self, prompt_tokens: int | None, completion_tokens: int | None) -> None:
        prompt = int(prompt_tokens or 0)
        completion = int(completion_tokens or 0)
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.llm_calls += 1
        self.estimated_cost_usd += (
            (prompt / 1000.0) * settings.usd_per_1k_prompt_tokens
            + (completion / 1000.0) * settings.usd_per_1k_completion_tokens
        )

    def as_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "llm_calls": self.llm_calls,
            "embedding_calls": self.embedding_calls,
            "retries": self.retries,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "latencies_ms": self.latencies_ms,
            "cost_basis": "provider_usage_if_present_else_configured_rates",
        }


class Timer:
    def __init__(self) -> None:
        self._start = perf_counter()

    def ms(self) -> float:
        return round((perf_counter() - self._start) * 1000.0, 3)
