"""Seed agent_eval_datasets and agent_eval_cases from the CI eval dataset."""

from __future__ import annotations

import asyncio
from pathlib import Path

import sqlalchemy as sa

from database import session_scope
from database.models.agent_runtime import AgentCapability, AgentEvalCase, AgentEvalDataset
from ia_investing.ai.eval_datasets import EvalCaseFile, EvalDatasetFile, load_eval_dataset


def _build_logical_id(capability: str, version: int) -> str:
    return f"{capability}/v{version}"


async def main() -> None:
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
            raise RuntimeError(
                f"Capabilities not found in DB, create them first: {sorted(missing)}"
            )

        for capability, cases in dataset_file.capabilities.items():
            logical_id = _build_logical_id(capability, dataset_file.version)
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
                        input_payload=cast_input(case),
                        expected_payload=case.expected,
                        tags=case.tags,
                    )
                )

            print(f"  seeded {len(cases)} cases for {logical_id}")

        await session.commit()
        print(f"seed-eval-datasets-ok path={dataset_path} capabilities={len(dataset_file.capabilities)}")


def cast_input(case: EvalCaseFile) -> dict[str, object]:
    return case.input


if __name__ == "__main__":
    asyncio.run(main())
