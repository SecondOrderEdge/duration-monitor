"""Tests for point-in-time percentile ranks.

The first test in this file is the regression test for Deviation D1 and is the
most important test in the project: it asserts that a percentile computed at date
t never changes when later data arrives. If it fails, every backtest result is
contaminated by hindsight.
"""

import numpy as np
import pandas as pd
import pytest

from src.calculations.percentiles import (
    percentile_of_latest,
    point_in_time_percentile,
    trailing_zscore,
)


def test_percentiles_do_not_change_when_future_data_arrives():
    """The defining property: no look-ahead."""
    rng = np.random.default_rng(20260814)
    full = pd.Series(rng.normal(size=200))

    complete = point_in_time_percentile(full, min_periods=12)

    # Recompute using only the first 50 observations, as of that moment in time.
    truncated = point_in_time_percentile(full.iloc[:50], min_periods=12)

    pd.testing.assert_series_equal(complete.iloc[:50], truncated)


def test_monotonic_increasing_series_is_always_at_its_own_maximum():
    """A strictly rising series is at a new high at every point.

    Full-sample ranking would return 20, 40, 60, 80, 100 here. Point-in-time
    ranking returns 100 throughout, because each value is the highest *so far*.
    This is the clearest illustration of the difference.
    """
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = point_in_time_percentile(s, min_periods=1)
    assert result.tolist() == [100.0, 100.0, 100.0, 100.0, 100.0]


def test_monotonic_decreasing_series_hand_computed():
    """Hand-computed: each value is the minimum of the window to date.

    i=0 -> 1 of 1 at or below      -> 100
    i=1 -> 1 of 2                  ->  50
    i=2 -> 1 of 3                  ->  33.333...
    i=3 -> 1 of 4                  ->  25
    i=4 -> 1 of 5                  ->  20
    """
    s = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0])
    result = point_in_time_percentile(s, min_periods=1)
    expected = [100.0, 50.0, 100 / 3, 25.0, 20.0]
    np.testing.assert_allclose(result.to_numpy(), expected)


def test_min_periods_suppresses_early_readings():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = point_in_time_percentile(s, min_periods=3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2:].notna().all()


def test_trailing_window_forgets_old_observations():
    """With window=3, the early spike drops out of the comparison set."""
    s = pd.Series([100.0, 1.0, 2.0, 3.0, 4.0])
    result = point_in_time_percentile(s, min_periods=3, window=3)

    # i=3: window is [1, 2, 3], value 3 -> 3 of 3 at or below -> 100
    assert result.iloc[3] == pytest.approx(100.0)
    # i=4: window is [2, 3, 4], value 4 -> 100. The 100.0 at i=0 is gone.
    assert result.iloc[4] == pytest.approx(100.0)


def test_weak_and_mid_methods_differ_on_ties():
    s = pd.Series([1.0, 1.0])
    weak = point_in_time_percentile(s, min_periods=1, method="weak")
    mid = point_in_time_percentile(s, min_periods=1, method="mid")

    # Two tied values: 'weak' counts both as at-or-below (100), 'mid' splits (50).
    assert weak.iloc[1] == pytest.approx(100.0)
    assert mid.iloc[1] == pytest.approx(50.0)


def test_nan_observations_are_skipped_not_imputed():
    s = pd.Series([1.0, np.nan, 3.0, 4.0])
    result = point_in_time_percentile(s, min_periods=2)

    assert np.isnan(result.iloc[1])
    # i=2 ranks 3.0 against the two real observations [1, 3] -> 100.
    assert result.iloc[2] == pytest.approx(100.0)


def test_window_smaller_than_min_periods_is_rejected():
    s = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="at least min_periods"):
        point_in_time_percentile(s, min_periods=5, window=3)


def test_invalid_method_is_rejected():
    with pytest.raises(ValueError, match="method must be"):
        point_in_time_percentile(pd.Series([1.0]), min_periods=1, method="strong")


def test_percentile_of_latest_uses_the_last_valid_observation():
    s = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0, np.nan])
    assert percentile_of_latest(s, min_periods=1) == pytest.approx(20.0)


class TestTrailingZscore:
    def test_excludes_the_current_observation_hand_computed(self):
        """Prior window at i=2 is [1, 2]: mean 1.5, sample sd sqrt(0.5).

        z = (3 - 1.5) / 0.7071068 = 2.1213203
        """
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 10.0])
        z = trailing_zscore(s, min_periods=2)

        assert np.isnan(z.iloc[0])  # no prior observations
        assert np.isnan(z.iloc[1])  # only one prior, cannot form a sd
        assert z.iloc[2] == pytest.approx(2.1213203, rel=1e-6)

    def test_constant_history_yields_nan_not_infinity(self):
        """Zero standard deviation means the z-score is undefined, not infinite."""
        s = pd.Series([5.0, 5.0, 5.0, 9.0])
        z = trailing_zscore(s, min_periods=2)
        assert np.isnan(z.iloc[3])

    def test_min_periods_below_two_is_rejected(self):
        with pytest.raises(ValueError, match="at least 2"):
            trailing_zscore(pd.Series([1.0, 2.0]), min_periods=1)
