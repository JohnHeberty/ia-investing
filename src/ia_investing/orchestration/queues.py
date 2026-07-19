from enum import StrEnum


class Capability(StrEnum):
    DATA_INGESTION = "data-ingestion"
    DOCUMENT_PROCESSING = "document-processing"
    RESEARCH_AGENTS = "research-agents"
    PORTFOLIO_RISK = "portfolio-risk"
    NOTIFICATIONS = "notifications"


TASK_QUEUES: dict[Capability, str] = {capability: capability.value for capability in Capability}
