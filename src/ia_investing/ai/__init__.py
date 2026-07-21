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
from .errors import AiProviderError, GuardrailViolation

__all__ = [
    "ALL_AGENTS",
    "AiProviderError",
    "AgentConfig",
    "AgentResult",
    "AgentRunner",
    "CRITIC_AGENT",
    "FILING_ANALYST",
    "FUNDAMENTALIST_ANALYST",
    "GuardrailViolation",
    "INVESTMENT_COMMITTEE",
    "NEWS_ANALYST",
    "RESEARCH_COORDINATOR",
    "RISK_DIRECTOR",
]
