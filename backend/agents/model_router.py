"""
OmniEngine — Dynamic Model Router

Selects the optimal LLM based on task complexity, token count,
vision requirements, and real-time API latency. Implements
fallback chains across providers (OpenAI, Anthropic, Google).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from backend.core.config import Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

# =============================================================================
# Model Registry
# =============================================================================


@dataclass
class ModelSpec:
    """Specification for a model available in the routing pool."""

    name: str
    provider: Literal["openai", "anthropic", "google"]
    tier: Literal["small", "medium", "large", "reasoning"]
    max_context_tokens: int
    supports_vision: bool = False
    supports_tools: bool = True
    supports_streaming: bool = True
    cost_per_1k_input: float = 0.0  # USD per 1K input tokens
    cost_per_1k_output: float = 0.0  # USD per 1K output tokens


# Default model registry — can be extended via configuration
MODEL_REGISTRY: dict[str, ModelSpec] = {
    # OpenAI
    "gpt-4o-mini": ModelSpec(
        name="gpt-4o-mini",
        provider="openai",
        tier="small",
        max_context_tokens=128_000,
        supports_vision=True,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    ),
    "gpt-4o": ModelSpec(
        name="gpt-4o",
        provider="openai",
        tier="medium",
        max_context_tokens=128_000,
        supports_vision=True,
        cost_per_1k_input=0.0025,
        cost_per_1k_output=0.01,
    ),
    "o1": ModelSpec(
        name="o1",
        provider="openai",
        tier="reasoning",
        max_context_tokens=200_000,
        supports_vision=True,
        supports_streaming=False,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.06,
    ),
    # Anthropic
    "claude-sonnet-4-20250514": ModelSpec(
        name="claude-sonnet-4-20250514",
        provider="anthropic",
        tier="large",
        max_context_tokens=200_000,
        supports_vision=True,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
    ),
    "claude-haiku-3-5": ModelSpec(
        name="claude-3-5-haiku-20241022",
        provider="anthropic",
        tier="small",
        max_context_tokens=200_000,
        supports_vision=True,
        cost_per_1k_input=0.0008,
        cost_per_1k_output=0.004,
    ),
    # Google
    "gemini-1.5-pro": ModelSpec(
        name="gemini-1.5-pro",
        provider="google",
        tier="large",
        max_context_tokens=1_000_000,
        supports_vision=True,
        cost_per_1k_input=0.00125,
        cost_per_1k_output=0.005,
    ),
    "gemini-1.5-flash": ModelSpec(
        name="gemini-1.5-flash",
        provider="google",
        tier="small",
        max_context_tokens=1_000_000,
        supports_vision=True,
        cost_per_1k_input=0.000075,
        cost_per_1k_output=0.0003,
    ),
}


# =============================================================================
# Latency Tracker
# =============================================================================


@dataclass
class ProviderLatency:
    """Tracks exponential moving average of API latency per provider."""

    latencies: dict[str, float] = field(
        default_factory=lambda: {
            "openai": 0.5,
            "anthropic": 0.5,
            "google": 0.5,
        }
    )
    alpha: float = 0.3  # EMA smoothing factor

    def update(self, provider: str, latency_seconds: float) -> None:
        """Update the EMA for a provider."""
        current = self.latencies.get(provider, 0.5)
        self.latencies[provider] = self.alpha * latency_seconds + (1 - self.alpha) * current

    def get(self, provider: str) -> float:
        """Get current EMA latency for a provider."""
        return self.latencies.get(provider, 1.0)

    def fastest_provider(self) -> str:
        """Return the provider with the lowest latency."""
        return min(self.latencies, key=self.latencies.get)  # type: ignore[arg-type]


# Module-level latency tracker (shared across requests)
_provider_latency = ProviderLatency()


def get_latency_tracker() -> ProviderLatency:
    """Return the global latency tracker."""
    return _provider_latency


# =============================================================================
# Model Router
# =============================================================================


class ModelRouter:
    """
    Dynamically selects the optimal LLM based on:
      1. Task complexity / model tier requirement
      2. Vision capability needs
      3. Token count vs context window
      4. API latency (prefer faster providers when quality is equal)
      5. Explicit user model preference
      6. Fallback chain on provider failure
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.latency = get_latency_tracker()

    def select_model(
        self,
        tier: str = "medium",
        needs_vision: bool = False,
        token_count: int = 0,
        preference: str | None = None,
    ) -> ModelSpec:
        """
        Select the best model for the given requirements.

        Args:
            tier: Required model tier (small/medium/large/reasoning).
            needs_vision: Whether the task requires vision capability.
            token_count: Estimated token count of the conversation.
            preference: User's explicit model preference (overrides routing).

        Returns:
            The selected ModelSpec.
        """
        # User preference override
        if preference and preference in MODEL_REGISTRY:
            spec = MODEL_REGISTRY[preference]
            if self._check_api_key(spec.provider):
                logger.info("Using user-preferred model: %s", spec.name)
                return spec
            logger.warning("Preferred model %s unavailable (no API key), falling back", preference)

        # Filter candidates by requirements
        candidates = self._filter_candidates(tier, needs_vision, token_count)

        if not candidates:
            # Broaden search: try one tier up
            tier_order = ["small", "medium", "large", "reasoning"]
            current_idx = tier_order.index(tier) if tier in tier_order else 1
            for fallback_tier in tier_order[current_idx:]:
                candidates = self._filter_candidates(fallback_tier, needs_vision, token_count)
                if candidates:
                    break

        if not candidates:
            # Last resort: use any available model
            candidates = [
                spec for spec in MODEL_REGISTRY.values() if self._check_api_key(spec.provider)
            ]

        if not candidates:
            from backend.core.exceptions import ModelRoutingError

            raise ModelRoutingError(
                "No models available. Please configure at least one LLM API key.",
                details={"tier": tier, "needs_vision": needs_vision},
            )

        # Sort by: latency (ascending), then cost (ascending)
        candidates.sort(
            key=lambda s: (
                self.latency.get(s.provider),
                s.cost_per_1k_input + s.cost_per_1k_output,
            )
        )

        selected = candidates[0]
        logger.info(
            "Model selected: %s (tier=%s, provider=%s, latency=%.2fs)",
            selected.name,
            selected.tier,
            selected.provider,
            self.latency.get(selected.provider),
        )
        return selected

    def get_fallback_chain(self, primary: ModelSpec) -> list[ModelSpec]:
        """
        Build a fallback chain for the given primary model.

        Returns models from other providers at the same or higher tier.
        """
        chain: list[ModelSpec] = []

        # First: try configured fallback chain
        for model_name in self.settings.fallback_chain_list:
            if model_name in MODEL_REGISTRY and model_name != primary.name:
                spec = MODEL_REGISTRY[model_name]
                if self._check_api_key(spec.provider):
                    chain.append(spec)

        # Then: add any remaining available models not in the chain
        for spec in MODEL_REGISTRY.values():
            if (
                spec.name != primary.name
                and spec not in chain
                and self._check_api_key(spec.provider)
            ):
                chain.append(spec)

        return chain

    def create_llm(
        self,
        spec: ModelSpec,
        temperature: float | None = None,
        streaming: bool = True,
    ) -> BaseChatModel:
        """
        Instantiate a LangChain chat model from a ModelSpec.

        Args:
            spec: The model specification to instantiate.
            temperature: Sampling temperature. Defaults vary by provider.
            streaming: Whether to enable streaming.

        Returns:
            A configured BaseChatModel instance.
        """
        temp = temperature if temperature is not None else 0.7
        kwargs: dict[str, Any] = {
            "temperature": temp,
            "streaming": streaming and spec.supports_streaming,
        }

        if spec.provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=spec.name,
                api_key=self.settings.openai_api_key,
                **kwargs,
            )

        if spec.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=spec.name,
                api_key=self.settings.anthropic_api_key,
                max_tokens=4096,
                **kwargs,
            )

        if spec.provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=spec.name,
                google_api_key=self.settings.google_genai_api_key,
                **kwargs,
            )

        from backend.core.exceptions import ModelRoutingError

        raise ModelRoutingError(f"Unknown provider: {spec.provider}")

    def estimate_cost(
        self,
        spec: ModelSpec,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate the cost of a model invocation in USD."""
        input_cost = (input_tokens / 1000) * spec.cost_per_1k_input
        output_cost = (output_tokens / 1000) * spec.cost_per_1k_output
        return round(input_cost + output_cost, 6)

    def _filter_candidates(
        self,
        tier: str,
        needs_vision: bool,
        token_count: int,
    ) -> list[ModelSpec]:
        """Filter models by tier, vision, context window, and API key availability."""
        candidates: list[ModelSpec] = []

        for spec in MODEL_REGISTRY.values():
            if spec.tier != tier:
                continue
            if needs_vision and not spec.supports_vision:
                continue
            if token_count > 0 and token_count > spec.max_context_tokens * 0.9:
                continue
            if not self._check_api_key(spec.provider):
                continue
            candidates.append(spec)

        return candidates

    def _check_api_key(self, provider: str) -> bool:
        """Check if the API key for a provider is configured."""
        if provider == "openai":
            return bool(
                self.settings.openai_api_key
                and self.settings.openai_api_key != "sk-your-openai-api-key-here"
            )
        if provider == "anthropic":
            return bool(
                self.settings.anthropic_api_key
                and self.settings.anthropic_api_key != "sk-ant-your-anthropic-api-key-here"
            )
        if provider == "google":
            return bool(
                self.settings.google_genai_api_key
                and self.settings.google_genai_api_key != "your-google-genai-api-key-here"
            )
        return False
