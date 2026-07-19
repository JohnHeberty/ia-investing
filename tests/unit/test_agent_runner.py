from __future__ import annotations

from types import SimpleNamespace

from ia_investing.ai._runner import _extract_usage


def test_extract_usage_uses_sdk_context_wrapper() -> None:
    result = SimpleNamespace(context_wrapper=SimpleNamespace(usage=SimpleNamespace(input_tokens=13, output_tokens=8)))

    assert _extract_usage(result) == (13, 8)


def test_extract_usage_defaults_to_zero() -> None:
    assert _extract_usage(SimpleNamespace()) == (0, 0)
