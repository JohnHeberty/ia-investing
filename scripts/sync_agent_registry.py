from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from database.core import session_scope
from ia_investing.ai.artifacts import ArtifactLoader
from ia_investing.application.agent_runtime import AgentRegistryService


async def synchronize(actor: str) -> None:
    async with session_scope() as session:
        versions = await AgentRegistryService(session, ArtifactLoader(Path("prompts"))).synchronize(actor)
        for version in versions:
            print(f"capability={version.capability_id} version={version.version} status={version.status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and synchronize versioned agent artifacts")
    parser.add_argument("--actor", required=True, help="Deployment or operator identity recorded in the audit log")
    arguments = parser.parse_args()
    asyncio.run(synchronize(arguments.actor))


if __name__ == "__main__":
    main()
