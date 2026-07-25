from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50 / 1_000_000, 10.00 / 1_000_000),
    "gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
    "o3-mini": (1.10 / 1_000_000, 4.40 / 1_000_000),
    # Qwen (via LiteLLM)
    "qwen-max": (2.80 / 1_000_000, 5.60 / 1_000_000),
    "qwen-plus": (0.80 / 1_000_000, 2.40 / 1_000_000),
    "qwen-turbo": (0.30 / 1_000_000, 0.60 / 1_000_000),
    # Anthropic / Claude
    "claude-sonnet-4-20250514": (3.00 / 1_000_000, 15.00 / 1_000_000),
    "claude-3-5-haiku-20241022": (0.80 / 1_000_000, 4.00 / 1_000_000),
    # Embeddings
    "text-embedding-3-small": (0.02 / 1_000_000, 0.0 / 1_000_000),
    "text-embedding-3-large": (0.13 / 1_000_000, 0.0 / 1_000_000),
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    if model not in _MODEL_PRICING:
        logger.warning("Unknown model '%s' for cost estimation, using gpt-4o fallback pricing", model)
    input_price, output_price = _MODEL_PRICING.get(model, (2.50 / 1_000_000, 10.00 / 1_000_000))
    return prompt_tokens * input_price + completion_tokens * output_price
