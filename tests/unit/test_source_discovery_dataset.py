from __future__ import annotations

from pathlib import Path

from ia_investing.ai.eval_datasets import load_eval_dataset

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "eval_dataset.json"


def _dataset():
    ds, _ = load_eval_dataset(FIXTURE_PATH)
    return ds.capabilities.get("company_source_discovery", [])


def test_capability_has_six_cases() -> None:
    cases = _dataset()
    assert len(cases) == 6


def test_three_normal_cases() -> None:
    cases = _dataset()
    normal = [c for c in cases if "normal" in c.tags]
    assert len(normal) == 3


def test_three_adversarial_cases() -> None:
    cases = _dataset()
    adversarial = [c for c in cases if "normal" not in c.tags]
    assert len(adversarial) == 3


def test_all_adversarial_tags_present() -> None:
    cases = _dataset()
    tags = {tag for case in cases for tag in case.tags}
    assert "prompt_injection" in tags
    assert "conflicting_evidence" in tags
    assert "future_date" in tags


def test_all_cases_have_ticker_input() -> None:
    cases = _dataset()
    for case in cases:
        assert "ticker" in case.input, f"{case.key} missing ticker"


def test_all_cases_have_legal_name_hint() -> None:
    cases = _dataset()
    for case in cases:
        assert "legal_name_hint" in case.input, f"{case.key} missing legal_name_hint"


def test_all_normal_cases_have_identity_confidence() -> None:
    cases = _dataset()
    for case in cases:
        if "normal" in case.tags:
            assert "identity_confidence" in case.expected


def test_injection_case_has_blocked_flag() -> None:
    cases = _dataset()
    injection = next(c for c in cases if "prompt_injection" in c.tags)
    assert injection.expected.get("blocked") is True


def test_future_date_case_has_blocked_flag() -> None:
    cases = _dataset()
    future = next(c for c in cases if "future_date" in c.tags)
    assert future.expected.get("blocked") is True


def test_conflict_case_has_contradictions_flag() -> None:
    cases = _dataset()
    conflict = next(c for c in cases if "conflicting_evidence" in c.tags)
    assert conflict.expected.get("has_contradictions") is True


def test_case_keys_unique() -> None:
    cases = _dataset()
    keys = [c.key for c in cases]
    assert len(keys) == len(set(keys))
