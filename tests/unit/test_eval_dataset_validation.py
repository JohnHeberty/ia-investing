from __future__ import annotations

from pathlib import Path

from ia_investing.ai.eval_datasets import (
    REQUIRED_ADVERSARIAL_TAGS,
    REQUIRED_CAPABILITIES,
    load_eval_dataset,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "eval_dataset.json"


def test_dataset_loads_without_error() -> None:
    _dataset, checksum = load_eval_dataset(FIXTURE_PATH)
    assert isinstance(checksum, str)
    assert len(checksum) == 64


def test_dataset_version_is_positive() -> None:
    dataset, _ = load_eval_dataset(FIXTURE_PATH)
    assert dataset.version > 0


def test_all_seven_capabilities_present() -> None:
    dataset, _ = load_eval_dataset(FIXTURE_PATH)
    assert set(dataset.capabilities.keys()) == REQUIRED_CAPABILITIES


def test_each_capability_has_at_least_one_case() -> None:
    dataset, _ = load_eval_dataset(FIXTURE_PATH)
    for cap in REQUIRED_CAPABILITIES:
        assert len(dataset.capabilities[cap]) >= 1, f"{cap} has no cases"


def test_all_three_adversarial_tags_present() -> None:
    dataset, _ = load_eval_dataset(FIXTURE_PATH)
    all_tags: set[str] = set()
    for cases in dataset.capabilities.values():
        for case in cases:
            all_tags.update(case.tags)
    missing = REQUIRED_ADVERSARIAL_TAGS - all_tags
    assert not missing, f"missing adversarial tags: {sorted(missing)}"


def test_case_keys_unique_within_capability() -> None:
    dataset, _ = load_eval_dataset(FIXTURE_PATH)
    for cap, cases in dataset.capabilities.items():
        keys = [c.key for c in cases]
        assert len(keys) == len(set(keys)), f"duplicate keys in {cap}"


def test_all_cases_have_input_and_expected() -> None:
    dataset, _ = load_eval_dataset(FIXTURE_PATH)
    for cap, cases in dataset.capabilities.items():
        for case in cases:
            assert case.input, f"{cap}/{case.key} missing input"
            assert case.expected, f"{cap}/{case.key} missing expected"
