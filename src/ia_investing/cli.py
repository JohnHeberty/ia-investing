from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from pydantic import ValidationError

from .settings import Settings


def check_config() -> None:
    """Validate configuration without printing values or secrets."""
    try:
        settings = Settings()
    except ValidationError as exc:
        locations = sorted({".".join(str(part) for part in error["loc"]) or "root" for error in exc.errors()})
        print("Configuration invalid: " + ", ".join(locations), file=sys.stderr)
        raise SystemExit(1) from None
    print(f"Configuration valid for environment={settings.application.environment}")


def seed_eval_datasets() -> None:
    """Seed agent eval datasets from the CI eval dataset JSON."""
    import sqlalchemy as sa

    from database import session_scope
    from database.models.agent_runtime import AgentCapability, AgentEvalCase, AgentEvalDataset
    from ia_investing.ai.eval_datasets import EvalDatasetFile, load_eval_dataset

    async def _run() -> None:
        dataset_path = Path("evals/agents/v1.json")
        dataset_file: EvalDatasetFile
        dataset_file, sha256_hash = load_eval_dataset(dataset_path)

        async with session_scope() as session:
            capabilities = {
                row.logical_id: row.id
                for row in await session.execute(
                    sa.select(AgentCapability).where(
                        AgentCapability.logical_id.in_(sorted(dataset_file.capabilities))
                    )
                )
            }

            missing = set(dataset_file.capabilities) - set(capabilities)
            if missing:
                print(f"Capabilities not found in DB: {sorted(missing)}", file=sys.stderr)
                raise SystemExit(1)

            seeded = 0
            for capability, cases in dataset_file.capabilities.items():
                logical_id = f"{capability}/v{dataset_file.version}"
                capability_id = capabilities[capability]

                existing = await session.scalar(
                    sa.select(AgentEvalDataset.id).where(
                        AgentEvalDataset.logical_id == logical_id,
                        AgentEvalDataset.version == dataset_file.version,
                    )
                )
                if existing is not None:
                    print(f"  dataset exists: {logical_id}")
                    continue

                dataset = AgentEvalDataset(
                    logical_id=logical_id,
                    capability_id=capability_id,
                    version=dataset_file.version,
                    sha256=sha256_hash,
                )
                session.add(dataset)
                await session.flush()

                for case in cases:
                    session.add(
                        AgentEvalCase(
                            dataset_id=dataset.id,
                            case_key=case.key,
                            input_payload=case.input,
                            expected_payload=case.expected,
                            tags=case.tags,
                        )
                    )
                seeded += len(cases)
                print(f"  seeded {len(cases)} cases for {logical_id}")

            await session.commit()
            print(
                f"seed-eval-datasets-ok path={dataset_path}"
                f" capabilities={len(dataset_file.capabilities)} cases={seeded}"
            )

    asyncio.run(_run())
