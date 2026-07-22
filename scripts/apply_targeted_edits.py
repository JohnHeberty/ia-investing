#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

AGENT_MODEL_HEADER = """class AgentRuntimeRun(Base):
    __tablename__ = "agent_runtime_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
"""
AGENT_MODEL_HEADER_WITH_TENANT = """class AgentRuntimeRun(Base):
    __tablename__ = "agent_runtime_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
"""
AGENT_UNIQUE = (
    '        sa.UniqueConstraint("capability_id", "idempotency_key", '
    'name="uq_agent_runtime_runs_capability_idempotency"),\n'
)
AGENT_TENANT_UNIQUE = """        sa.UniqueConstraint(
            "organization_id",
            "capability_id",
            "idempotency_key",
            name="uq_agent_runtime_runs_org_capability_idempotency",
        ),
"""
RESEARCH_MODEL_HEADER = """class ResearchCase(Base):
    __tablename__ = "research_cases"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
"""
RESEARCH_MODEL_HEADER_WITH_TENANT = """class ResearchCase(Base):
    __tablename__ = "research_cases"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
"""
RESEARCH_TENANT_UNIQUE = """        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_research_cases_organization_idempotency_key",
        ),
"""


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one match in {path}: found {count}\n--- expected ---\n{old}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_agent_model(root: Path) -> None:
    path = root / "src/database/models/agent_runtime.py"
    replace_once(path, AGENT_MODEL_HEADER, AGENT_MODEL_HEADER_WITH_TENANT)
    replace_once(path, AGENT_UNIQUE, AGENT_TENANT_UNIQUE)


def patch_research_model(root: Path) -> None:
    path = root / "src/database/models/research.py"
    replace_once(path, RESEARCH_MODEL_HEADER, RESEARCH_MODEL_HEADER_WITH_TENANT)
    replace_once(
        path,
        '    idempotency_key: Mapped[str] = mapped_column(sa.String(255), unique=True)\n',
        '    idempotency_key: Mapped[str] = mapped_column(sa.String(255))\n',
    )
    marker = (
        '        sa.CheckConstraint("request_hash ~ \'^[0-9a-f]{64}$\'", '
        'name="request_hash_format"),\n'
    )
    replace_once(path, marker, marker + RESEARCH_TENANT_UNIQUE)


def patch_agent_service(root: Path) -> None:
    path = root / "src/ia_investing/application/agent_runtime.py"
    replace_once(
        path,
        "        *,\n        capability: str,\n",
        "        *,\n        organization_id: UUID,\n        capability: str,\n",
    )
    replace_once(
        path,
        """                    AgentRuntimeRun.capability_id == definition.id,
                    AgentRuntimeRun.idempotency_key == idempotency_key,
""",
        """                    AgentRuntimeRun.organization_id == organization_id,
                    AgentRuntimeRun.capability_id == definition.id,
                    AgentRuntimeRun.idempotency_key == idempotency_key,
""",
    )
    replace_once(
        path,
        "        run = AgentRuntimeRun(\n            capability_id=definition.id,\n",
        """        run = AgentRuntimeRun(
            organization_id=organization_id,
            capability_id=definition.id,
""",
    )


def patch_research_service(root: Path) -> None:
    path = root / "src/ia_investing/application/research.py"
    replace_once(
        path,
        "class CreateResearchCase:\n    case_type: str\n",
        "class CreateResearchCase:\n    organization_id: UUID\n    case_type: str\n",
    )
    replace_once(
        path,
        '        payload = {\n            "case_type": self.case_type,\n',
        """        payload = {
            "organization_id": str(self.organization_id),
            "case_type": self.case_type,
""",
    )
    replace_once(
        path,
        "            select(ResearchCase).where(ResearchCase.idempotency_key == idempotency_key)\n",
        """            select(ResearchCase).where(
                ResearchCase.organization_id == command.organization_id,
                ResearchCase.idempotency_key == idempotency_key,
            )
""",
    )
    replace_once(
        path,
        "        case = ResearchCase(\n            case_type=command.case_type,\n",
        """        case = ResearchCase(
            organization_id=command.organization_id,
            case_type=command.case_type,
""",
    )


def patch_model_exports(root: Path) -> None:
    path = root / "src/database/models/__init__.py"
    replace_once(
        path,
        'from .portfolio import (  # noqa: F401\n',
        'from .operations import Operation, OperationDispatchOutbox  # noqa: F401'
        '\nfrom .portfolio import (  # noqa: F401\n',
    )


def patch_worker_settings(root: Path) -> None:
    path = root / "src/ia_investing/settings.py"
    replace_once(
        path,
        '        "data-ingestion",\n        "document-processing",\n        "research-agents",\n',
        '        "data-ingestion",\n        "research-agents",\n',
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    args = parser.parse_args()
    root = args.repository.resolve()
    patch_agent_model(root)
    patch_research_model(root)
    patch_agent_service(root)
    patch_research_service(root)
    patch_worker_settings(root)
    patch_model_exports(root)
    print("targeted tenant/runtime edits applied")


if __name__ == "__main__":
    main()
