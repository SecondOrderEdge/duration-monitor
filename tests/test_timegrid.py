"""Tests for the period-grid helpers."""

import numpy as np
import pandas as pd
import pytest

from src.calculations.timegrid import (
    ensure_complete,
    period_change,
    period_pct_change,
    to_period_index,
)


def _series(periods, values):
    return pd.Series(values, index=pd.PeriodIndex(periods, freq="M"))


def test_ensure_complete_inserts_missing_periods_as_nan():
    s = _series(["2024-01", "2024-04"], [1.0, 4.0])
    result = ensure_complete(s)

    assert len(result) == 4
    assert result.index.tolist() == pd.period_range("2024-01", "2024-04", freq="M").tolist()
    assert result.isna().sum() == 2


def test_ensure_complete_sorts_unordered_input():
    s = _series(["2024-03", "2024-01", "2024-02"], [3.0, 1.0, 2.0])
    assert ensure_complete(s).tolist() == [1.0, 2.0, 3.0]


def test_duplicate_periods_are_rejected():
    """Two rows for one month means an upstream error, not something to average."""
    s = _series(["2024-01", "2024-01"], [1.0, 2.0])
    with pytest.raises(ValueError, match="duplicate periods"):
        ensure_complete(s)


def test_non_period_index_is_rejected():
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-31", "2024-02-29"]))
    with pytest.raises(TypeError, match="expected a PeriodIndex"):
        ensure_complete(s)


def test_period_change_measures_calendar_distance_not_row_distance():
    """February missing: the 1-month change into March has no starting point."""
    s = _series(["2024-01", "2024-03"], [1.0, 3.0])
    change = period_change(s, 1)

    assert np.isnan(change.loc[pd.Period("2024-03", freq="M")])
    # A naive row-wise diff would have reported 2.0 here.


def test_period_change_over_a_complete_span():
    s = _series(["2024-01", "2024-02", "2024-03"], [1.0, 2.0, 5.0])
    assert period_change(s, 2).iloc[2] == pytest.approx(4.0)


def test_period_pct_change_does_not_forward_fill():
    s = _series(["2024-01", "2024-03"], [100.0, 150.0])
    assert np.isnan(period_pct_change(s, 1).loc[pd.Period("2024-03", freq="M")])


def test_period_pct_change_zero_base_is_nan_not_infinity():
    s = _series(["2024-01", "2024-02"], [0.0, 5.0])
    assert np.isnan(period_pct_change(s, 1).iloc[1])


def test_period_pct_change_hand_computed():
    s = _series(["2024-01", "2024-02"], [100.0, 125.0])
    assert period_pct_change(s, 1).iloc[1] == pytest.approx(0.25)


def test_non_positive_horizon_is_rejected():
    s = _series(["2024-01", "2024-02"], [1.0, 2.0])
    with pytest.raises(ValueError, match="must be positive"):
        period_change(s, 0)
    with pytest.raises(ValueError, match="must be positive"):
        period_pct_change(s, -1)


def test_to_period_index_rejects_unsupported_frequency():
    df = pd.DataFrame({"d": ["2024-01-31"], "v": [1.0]})
    with pytest.raises(ValueError, match="freq must be one of"):
        to_period_index(df, "d", "D")


def test_to_period_index_converts_and_drops_the_date_column():
    df = pd.DataFrame({"d": ["2024-01-31", "2024-02-29"], "v": [1.0, 2.0]})
    result = to_period_index(df, "d", "M")

    assert "d" not in result.columns
    assert isinstance(result.index, pd.PeriodIndex)
    assert result.index.tolist() == pd.period_range("2024-01", "2024-02", freq="M").tolist()
