"""Governed AI runtime for IA Investing OS."""

from ._config import (
    ALL_AGENTS,
    CRITIC_AGENT,
    FILING_ANALYST,
    FUNDAMENTALIST_ANALYST,
    INVESTMENT_COMMITTEE,
    NEWS_ANALYST,
    RESEARCH_COORDINATOR,
    RISK_DIRECTOR,
    AgentConfig,
)
from ._runner import AgentResult, AgentRunner
from .errors import AiProviderError, GuardrailViolationError
from .gateway import AIGateway, AnthropicGateway, GatewayProvider, OpenAIGateway, create_gateway_provider
from .gateway_errors import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from .rate_limiter import TokenBucketRateLimiter

__all__ = [
    "ALL_AGENTS",
    "CRITIC_AGENT",
    "FILING_ANALYST",
    "FUNDAMENTALIST_ANALYST",
    "INVESTMENT_COMMITTEE",
    "NEWS_ANALYST",
    "RESEARCH_COORDINATOR",
    "RISK_DIRECTOR",
    "AIGateway",
    "AgentConfig",
    "AgentResult",
    "AgentRunner",
    "AiProviderError",
    "AnthropicGateway",
    "GatewayProvider",
    "GuardrailViolationError",
    "OpenAIGateway",
    "ProviderAuthError",
    "ProviderBadRequestError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "TokenBucketRateLimiter",
    "create_gateway_provider",
]
