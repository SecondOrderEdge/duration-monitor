"""Tests for weighted average maturity.

The core fixture is three securities with WAM computed by hand in the docstring
below, so the test validates the implementation against arithmetic rather than
against a previous run of the same code.
"""

import numpy as np
import pandas as pd
import pytest

from src.calculations.wam import (
    DAYS_PER_YEAR,
    maturity_buckets,
    wam_series,
    weighted_average_maturity,
)

VALUATION = pd.Timestamp("2025-01-01")


@pytest.fixture
def three_securities() -> pd.DataFrame:
    """Hand-computed fixture, valued at 2025-01-01.

    | security | amount | maturity   | days | years = days/365.25 |
    |----------|--------|------------|------|---------------------|
    | A        |    100 | 2026-01-01 |  365 | 0.999315537         |
    | B        |    200 | 2030-01-01 | 1826 | 4.999315537         |
    | C        |    300 | 2035-01-01 | 3652 | 9.998631075         |

    Weighted sum = 100(0.999315537) + 200(4.999315537) + 300(9.998631075)
                 =  99.9315537 + 999.8631074 + 2999.5893225
                 = 4099.3839836
    Total amount = 600
    WAM          = 4099.3839836 / 600 = 6.8323066...
    """
    return pd.DataFrame(
        {
            "cusip": ["A", "B", "C"],
            "amount_outstanding": [100.0, 200.0, 300.0],
            "maturity_date": pd.to_datetime(["2026-01-01", "2030-01-01", "2035-01-01"]),
        }
    )


def test_day_counts_underlying_the_fixture(three_securities):
    """Guard the fixture's own arithmetic: confirm the stated day counts."""
    days = (three_securities["maturity_date"] - VALUATION).dt.days.tolist()
    assert days == [365, 1826, 3652]


def test_wam_matches_hand_computation(three_securities):
    expected = (
        100 * (365 / DAYS_PER_YEAR)
        + 200 * (1826 / DAYS_PER_YEAR)
        + 300 * (3652 / DAYS_PER_YEAR)
    ) / 600
    assert expected == pytest.approx(6.8323066, rel=1e-7)
    assert weighted_average_maturity(three_securities, VALUATION) == pytest.approx(
        expected
    )


def test_maturity_buckets_are_cumulative_and_inclusive(three_securities):
    """A at 0.9993y falls in every bucket; B at 4.9993y falls in 5y but not 3y."""
    buckets = maturity_buckets(three_securities, VALUATION)

    assert buckets["within_1y"] == pytest.approx(100 / 600)
    assert buckets["within_2y"] == pytest.approx(100 / 600)
    assert buckets["within_3y"] == pytest.approx(100 / 600)
    assert buckets["within_5y"] == pytest.approx(300 / 600)


def test_security_maturing_on_the_valuation_date_contributes_zero_years():
    df = pd.DataFrame(
        {
            "amount_outstanding": [100.0, 100.0],
            "maturity_date": pd.to_datetime(["2025-01-01", "2027-01-01"]),
        }
    )
    # Second security: 2025-01-01 to 2027-01-01 is 730 days (neither year is a
    # leap year), 730 / 365.25 = 1.99863...; averaged against zero -> half that.
    assert (pd.Timestamp("2027-01-01") - VALUATION).days == 730
    expected = (0.0 + 100 * (730 / DAYS_PER_YEAR)) / 200
    assert weighted_average_maturity(df, VALUATION) == pytest.approx(expected)


def test_matured_security_raises_rather_than_going_negative():
    """A negative time to maturity would silently drag WAM down."""
    df = pd.DataFrame(
        {
            "amount_outstanding": [100.0],
            "maturity_date": pd.to_datetime(["2024-06-01"]),
        }
    )
    with pytest.raises(ValueError, match="mature before the valuation date"):
        weighted_average_maturity(df, VALUATION)


def test_zero_outstanding_returns_nan_not_a_division_error():
    df = pd.DataFrame(
        {
            "amount_outstanding": [0.0, 0.0],
            "maturity_date": pd.to_datetime(["2026-01-01", "2030-01-01"]),
        }
    )
    assert np.isnan(weighted_average_maturity(df, VALUATION))
    assert np.isnan(maturity_buckets(df, VALUATION)["within_1y"])


def test_missing_maturity_date_raises(three_securities):
    df = three_securities.copy()
    df.loc[1, "maturity_date"] = pd.NaT
    with pytest.raises(ValueError, match="missing or unparseable maturity_date"):
        weighted_average_maturity(df, VALUATION)


def test_negative_amount_raises(three_securities):
    df = three_securities.copy()
    df.loc[0, "amount_outstanding"] = -100.0
    with pytest.raises(ValueError, match="negative values"):
        weighted_average_maturity(df, VALUATION)


def test_mixed_amount_basis_raises(three_securities):
    """Par and inflation-adjusted amounts cannot be weighted together (D2/D9)."""
    df = three_securities.copy()
    df["amount_basis"] = ["PAR", "PAR", "INFLATION_ADJUSTED"]
    with pytest.raises(ValueError, match="mixed amount_basis"):
        weighted_average_maturity(df, VALUATION)


def test_missing_required_column_raises():
    with pytest.raises(ValueError, match="missing required columns"):
        weighted_average_maturity(pd.DataFrame({"amount_outstanding": [1.0]}), VALUATION)


def test_wam_series_values_each_snapshot_at_its_own_date():
    """The same security is one year shorter when valued one year later."""
    df = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(
                ["2025-01-01", "2025-01-01", "2026-01-01", "2026-01-01"]
            ),
            "amount_outstanding": [100.0, 200.0, 100.0, 200.0],
            "maturity_date": pd.to_datetime(
                ["2026-01-01", "2030-01-01", "2026-01-01", "2030-01-01"]
            ),
        }
    )
    result = wam_series(df)

    assert len(result) == 2
    first, second = result["wam_years"].tolist()
    # 2025 snapshot: (100*365 + 200*1826) / 300 / 365.25
    assert first == pytest.approx((100 * 365 + 200 * 1826) / 300 / DAYS_PER_YEAR)
    # One year on, both securities are 365 days shorter.
    assert second == pytest.approx((100 * 0 + 200 * 1461) / 300 / DAYS_PER_YEAR)
    assert second < first
