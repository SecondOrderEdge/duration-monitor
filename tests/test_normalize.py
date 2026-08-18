"""Tests for the raw → normalized transformation and its reconciliation check.

The cases that matter here are the ones that produce a tidy, plausible series
rather than an error: a security class renamed mid-history silently truncates,
and a units mistake rescales everything by a factor of a million while leaving
the shape of every chart identical.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.calculations.issuance import aggregate_net_issuance, net_issuance
from src.transformation.normalize import (
    MILLIONS,
    NormalizationError,
    normalize_debt_outstanding,
)
from src.validation.reconciliation import reconcile_components_to_total


def raw(rows: list[tuple]) -> pd.DataFrame:
    """(record_date, security_type_desc, security_class_desc, total_mil_amt)."""
    return pd.DataFrame(
        rows,
        columns=[
            "record_date", "security_type_desc", "security_class_desc", "total_mil_amt",
        ],
    ).astype({"record_date": "datetime64[ns]"})


MODERN = raw([
    ("2024-06-30", "Marketable", "Bills", 5_765_830.1),
    ("2024-06-30", "Marketable", "Notes", 14_046_707.4),
    ("2024-06-30", "Marketable", "Bonds", 4_581_064.9),
    ("2024-06-30", "Marketable", "Treasury Inflation-Protected Securities", 2_053_866.3),
    ("2024-06-30", "Marketable", "Floating Rate Notes", 598_011.4),
    ("2024-06-30", "Marketable", "Federal Financing Bank", 4_514.1),
    ("2024-06-30", "Total Marketable", "_", 27_049_994.2),
])


# --------------------------------------------------------------------------- #
# class mapping
# --------------------------------------------------------------------------- #


def test_modern_labels_map_to_canonical_classes():
    out = normalize_debt_outstanding(MODERN)
    assert set(out["security_class"]) == {
        "BILLS", "NOTES", "BONDS", "TIPS", "FRN", "OTHER", "TOTAL_MARKETABLE",
    }


def test_legacy_inflation_indexed_rows_merge_into_one_tips_row():
    """Before 2004-06, TIPS are two rows. Keyed on the modern label alone they vanish.

    The failure is silent: the remaining classes still form a tidy series, and
    TIPS simply appears to start in 2004.
    """
    legacy = raw([
        ("2004-05-31", "Marketable", "Bills", 1_000.0),
        ("2004-05-31", "Marketable", "Inflation-Indexed Notes", 152_777.4),
        ("2004-05-31", "Marketable", "Inflation-Indexed Bonds", 46_953.7),
        ("2004-05-31", "Total Marketable", "_", 200_731.1),
    ])
    out = normalize_debt_outstanding(legacy)
    tips = out.loc[out["security_class"] == "TIPS", "amount_outstanding"]

    assert len(tips) == 1                                    # merged, not duplicated
    assert tips.iloc[0] == pytest.approx((152_777.4 + 46_953.7) * MILLIONS)


def test_unmapped_class_raises_rather_than_dropping_out_of_the_totals():
    """A label never seen before is a rename or a new instrument. Both need a human."""
    novel = raw([
        ("2030-01-31", "Marketable", "Bills", 1.0),
        ("2030-01-31", "Marketable", "Perpetual Bonds", 5.0),
        ("2030-01-31", "Total Marketable", "_", 6.0),
    ])
    with pytest.raises(NormalizationError, match="Perpetual Bonds"):
        normalize_debt_outstanding(novel)


def test_nonmarketable_rows_are_excluded():
    with_nonmkt = pd.concat([
        MODERN,
        raw([("2024-06-30", "Nonmarketable", "Government Account Series", 7_499_786.5)]),
    ], ignore_index=True)

    out = normalize_debt_outstanding(with_nonmkt)
    assert len(out) == len(normalize_debt_outstanding(MODERN))


def test_grand_total_rows_are_not_mistaken_for_the_marketable_total():
    with_totals = pd.concat([
        MODERN,
        raw([("2024-06-30", "Total Public Debt Outstanding", "_", 34_831_634.0)]),
    ], ignore_index=True)

    out = normalize_debt_outstanding(with_totals)
    total = out.loc[out["security_class"] == "TOTAL_MARKETABLE", "amount_outstanding"]
    assert len(total) == 1
    assert total.iloc[0] == pytest.approx(27_049_994.2 * MILLIONS)


# --------------------------------------------------------------------------- #
# units and provenance
# --------------------------------------------------------------------------- #


def test_amounts_are_converted_from_millions_to_single_units():
    """A units error rescales everything and changes no chart's shape."""
    out = normalize_debt_outstanding(MODERN)
    bills = out.loc[out["security_class"] == "BILLS", "amount_outstanding"].iloc[0]
    assert bills == pytest.approx(5_765_830.1 * MILLIONS)
    assert bills > 1e12                                      # trillions, not millions


def test_tips_are_flagged_as_inflation_adjusted_and_others_as_par():
    out = normalize_debt_outstanding(MODERN).set_index("security_class")
    assert out.loc["TIPS", "amount_basis"] == "INFLATION_ADJUSTED"
    assert out.loc["BILLS", "amount_basis"] == "PAR"


def test_publication_date_is_missing_rather_than_estimated():
    """MSPD's publication lag is known; the endpoint does not carry the date.

    Deriving one would be indistinguishable downstream from a reported one.
    """
    out = normalize_debt_outstanding(MODERN)
    assert out["publication_date"].isna().all()


def test_provenance_is_stamped():
    stamp = pd.Timestamp("2026-08-18T12:00:00")
    out = normalize_debt_outstanding(MODERN, retrieval_date=stamp)
    assert (out["country"] == "US").all()
    assert (out["currency"] == "USD").all()
    assert (out["source"] == "fiscaldata/mspd_table_1").all()
    assert (out["retrieval_date"] == stamp).all()


def test_missing_required_column_raises():
    with pytest.raises(NormalizationError, match="total_mil_amt"):
        normalize_debt_outstanding(MODERN.drop(columns=["total_mil_amt"]))


# --------------------------------------------------------------------------- #
# reconciliation
# --------------------------------------------------------------------------- #


def test_components_reconcile_to_the_published_total():
    out = normalize_debt_outstanding(MODERN)
    result = reconcile_components_to_total(out, tolerance_pct=0.1)

    assert result.ok
    assert result.n_periods == 1
    result.raise_if_failed()          # must not raise


def test_reconciliation_breach_raises_with_the_offending_period():
    broken = MODERN.copy()
    broken.loc[broken["security_class_desc"] == "Bills", "total_mil_amt"] = 1.0

    out = normalize_debt_outstanding(broken)
    result = reconcile_components_to_total(out, tolerance_pct=0.1)

    assert not result.ok
    with pytest.raises(ValueError, match="published_total|differ"):
        result.raise_if_failed()


def test_rounding_residual_stays_within_tolerance():
    """Treasury rounds published figures; exact equality would fail every month."""
    rounded = MODERN.copy()
    rounded.loc[rounded["security_type_desc"] == "Total Marketable", "total_mil_amt"] += 1.0

    result = reconcile_components_to_total(
        normalize_debt_outstanding(rounded), tolerance_pct=0.1
    )
    assert result.ok
    assert result.max_abs_diff_pct < 0.001


# --------------------------------------------------------------------------- #
# quarterly aggregation
# --------------------------------------------------------------------------- #


def _monthly_debt(values: dict[str, list[float]], months: list[str]) -> pd.DataFrame:
    rows = []
    for cls, series in values.items():
        for month, v in zip(months, series):
            rows.append(
                {"observation_date": pd.Timestamp(month), "security_class": cls,
                 "amount_outstanding": v}
            )
    return pd.DataFrame(rows)


def test_quarterly_aggregation_sums_the_monthly_flows():
    """Net issuance is a flow: a quarter is the sum of its months' changes."""
    months = ["2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30",
              "2024-05-31", "2024-06-30", "2024-07-31"]
    debt = _monthly_debt({"BILLS": [100, 110, 125, 145, 150, 160, 170]}, months)

    q = aggregate_net_issuance(net_issuance(debt), freq="Q").set_index("period")
    # Q2 = (145-125) + (150-145) + (160-150) = 35
    assert q.loc["2024Q2", "net_issuance"] == pytest.approx(35)


def test_partial_trailing_quarter_is_voided_not_shown_short():
    """One month labelled as a quarter is a bar a third of its eventual height."""
    months = ["2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30"]
    debt = _monthly_debt({"BILLS": [100, 110, 125, 145]}, months)

    q = aggregate_net_issuance(net_issuance(debt), freq="Q").set_index("period")
    assert pd.isna(q.loc["2024Q2", "net_issuance"])       # only April present
    assert not q.loc["2024Q2", "period_complete"]


def test_quarter_containing_an_unmeasurable_month_is_voided():
    """The first month of any series has no prior observation to difference."""
    months = ["2024-01-31", "2024-02-29", "2024-03-31"]
    debt = _monthly_debt({"BILLS": [100, 110, 125]}, months)

    q = aggregate_net_issuance(net_issuance(debt), freq="Q").set_index("period")
    assert pd.isna(q.loc["2024Q1", "net_issuance"])       # January delta is NaN
