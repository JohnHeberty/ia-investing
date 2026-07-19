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
FUNDAMENTALIST_ANALYST = AgentConfig(
    "fundamentalist_analyst",
    "Analista Fundamentalista",
    "gpt-4o",
    0.2,
    4096,
    "fundamentalist/system.md",
    "schemas.ThesisVerdict",
)
CRITIC_AGENT = AgentConfig(
    "critic_agent",
    "Agente Crítico",
    "o3-mini",
    0.5,
    3072,
    "critic/system.md",
)
RISK_DIRECTOR = AgentConfig(
    "risk_director",
    "Diretor de Risco",
    "gpt-4o",
    0.1,
    3072,
    "risk_director/system.md",
    "schemas.RiskAssessment",
)
INVESTMENT_COMMITTEE = AgentConfig(
    "investment_committee",
    "Comitê de Investimento",
    "o3-mini",
    0.1,
    2048,
    "committee/system.md",
    "schemas.CommitteeDecision",
)
RESEARCH_COORDINATOR = AgentConfig(
    "research_coordinator",
    "Coordenador de Pesquisa",
    "gpt-4o",
    0.4,
    2048,
    "coordinator/system.md",
    "schemas.DiscoveryBrief",
)

ALL_AGENTS: dict[str, AgentConfig] = {
    config.name: config
    for config in (
        FILING_ANALYST,
        NEWS_ANALYST,
        FUNDAMENTALIST_ANALYST,
        CRITIC_AGENT,
        RISK_DIRECTOR,
        INVESTMENT_COMMITTEE,
        RESEARCH_COORDINATOR,
    )
}
