import pytest

from portfolio._transforms import TransformDefinition, percentile_ranks, winsorize, z_scores


def test_winsorization_is_versioned_and_caps_outlier() -> None:
    definition = TransformDefinition("transform-v1", 0.0, 0.75)
    assert winsorize([1.0, 2.0, 3.0, 100.0], definition)[-1] == pytest.approx(27.25)


def test_z_scores_of_constant_series_are_zero() -> None:
    assert z_scores([2.0, 2.0, 2.0]) == [0.0, 0.0, 0.0]


def test_percentile_ranks_preserve_order() -> None:
    assert percentile_ranks([30.0, 10.0, 20.0]) == [1.0, 0.0, 0.5]
