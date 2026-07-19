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

__all__ = [
    "ALL_AGENTS",
    "CRITIC_AGENT",
    "FILING_ANALYST",
    "FUNDAMENTALIST_ANALYST",
    "INVESTMENT_COMMITTEE",
    "NEWS_ANALYST",
    "RESEARCH_COORDINATOR",
    "RISK_DIRECTOR",
    "AgentConfig",
    "AgentResult",
    "AgentRunner",
]
