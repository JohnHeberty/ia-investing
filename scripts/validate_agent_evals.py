from pathlib import Path

from ia_investing.ai.eval_datasets import load_eval_dataset


def main() -> None:
    dataset, dataset_hash = load_eval_dataset(Path("evals/agents/v1.json"))
    case_count = sum(len(cases) for cases in dataset.capabilities.values())
    print(
        f"agent-evals-ok version={dataset.version} capabilities={len(dataset.capabilities)}",
        f"cases={case_count} sha256={dataset_hash}",
    )


if __name__ == "__main__":
    main()
