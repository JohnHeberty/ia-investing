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
    name="filing_analyst",
    display_name_pt="Analista de Documentos",
    model="gpt-4o",
    temperature=0.2,
    max_tokens=4096,
    system_prompt_path="prompts/filing_analyst/system.md",
    structured_output_type="schemas.FilingReviewVerdict",
)

NEWS_ANALYST = AgentConfig(
    name="news_analyst",
    display_name_pt="Analista de Notícias",
    model="gpt-4o",
    temperature=0.3,
    max_tokens=2048,
    system_prompt_path="prompts/news_analyst/system.md",
    structured_output_type="schemas.NewsAnalysis",
)

FUNDAMENTALIST_ANALYST = AgentConfig(
    name="fundamentalist_analyst",
    display_name_pt="Analista Fundamentalista",
    model="gpt-4o",
    temperature=0.2,
    max_tokens=4096,
    system_prompt_path="prompts/fundamentalist/system.md",
    structured_output_type="schemas.ThesisVerdict",
)

CRITIC_AGENT = AgentConfig(
    name="critic_agent",
    display_name_pt="Agente Crítico",
    model="o3-mini",
    temperature=0.5,
    max_tokens=3072,
    system_prompt_path="prompts/critic/system.md",
    structured_output_type=None,
)

RISK_DIRECTOR = AgentConfig(
    name="risk_director",
    display_name_pt="Diretor de Risco",
    model="gpt-4o",
    temperature=0.1,
    max_tokens=3072,
    system_prompt_path="prompts/risk_director/system.md",
    structured_output_type="schemas.RiskAssessment",
)

INVESTMENT_COMMITTEE = AgentConfig(
    name="investment_committee",
    display_name_pt="Comitê de Investimento",
    model="o3-mini",
    temperature=0.1,
    max_tokens=2048,
    system_prompt_path="prompts/committee/system.md",
    structured_output_type="schemas.CommitteeDecision",
)

RESEARCH_COORDINATOR = AgentConfig(
    name="research_coordinator",
    display_name_pt="Coordenador de Pesquisa",
    model="gpt-4o",
    temperature=0.4,
    max_tokens=2048,
    system_prompt_path="prompts/coordinator/system.md",
    structured_output_type="schemas.DiscoveryBrief",
)

ALL_AGENTS: dict[str, AgentConfig] = {
    cfg.name: cfg
    for cfg in [
        FILING_ANALYST,
        NEWS_ANALYST,
        FUNDAMENTALIST_ANALYST,
        CRITIC_AGENT,
        RISK_DIRECTOR,
        INVESTMENT_COMMITTEE,
        RESEARCH_COORDINATOR,
    ]
}
