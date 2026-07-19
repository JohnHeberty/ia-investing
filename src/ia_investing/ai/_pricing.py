from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50 / 1_000_000, 10.00 / 1_000_000),
    "o3-mini": (1.10 / 1_000_000, 4.40 / 1_000_000),
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    if model not in _MODEL_PRICING:
        logger.warning("Unknown model '%s' for cost estimation, using gpt-4o fallback pricing", model)
    input_price, output_price = _MODEL_PRICING.get(model, (2.50 / 1_000_000, 10.00 / 1_000_000))
    return prompt_tokens * input_price + completion_tokens * output_price
