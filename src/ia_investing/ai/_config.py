from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AgentConfig:
    name: str
    display_name_pt: str
    model: str
    temperature: float
    max_tokens: int
    system_prompt_path: str
    structured_output_type: str | None = None
    max_timeout_seconds: float = 300.0


FILING_ANALYST = AgentConfig(
    "filing_analyst",
    "Analista de Documentos",
    "gpt-4o",
    0.2,
    4096,
    "filing_analyst/system.md",
    "schemas.FilingReviewVerdict",
)
NEWS_ANALYST = AgentConfig(
    "news_analyst",
    "Analista de Notícias",
    "gpt-4o",
    0.3,
    2048,
    "news_analyst/system.md",
    "schemas.NewsAnalysis",
)
ALL_AGENTS: dict[str, AgentConfig] = {
    config.name: config
    for config in (
        FILING_ANALYST,
        NEWS_ANALYST,
    )
}
