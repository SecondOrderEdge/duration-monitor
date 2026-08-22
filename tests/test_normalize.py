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
    monthly_buyback_par,
    normalize_buybacks,
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


# --------------------------------------------------------------------------- #
# auctions
# --------------------------------------------------------------------------- #

from src.transformation.normalize import normalize_auctions, normalize_term  # noqa: E402


def test_original_term_gives_the_canonical_tenor():
    """`security_term` is the REMAINING term, so a reopened 10y reads 9-Year 11-Month.

    Grouping on that scatters one tenor across a dozen labels and leaves the
    trailing-window comparison with nothing to compare against.
    """
    assert normalize_term("10-Year") == "10Y"
    assert normalize_term("9-Year 11-Month") == "10Y"
    assert normalize_term("29-Year 9-Month") == "30Y"
    assert normalize_term("26-Week") == "26W"
    assert normalize_term("119-Day") == "119D"


def test_normalize_term_handles_missing_values():
    """pandas 3 keeps NaN through .astype(str), so non-strings reach this."""
    assert normalize_term(None) is None
    assert normalize_term(float("nan")) is None
    assert normalize_term("nan") is None
    assert normalize_term("") is None


def auction_rows() -> pd.DataFrame:
    return pd.DataFrame({
        "auction_date": pd.to_datetime(
            ["1985-03-01", "2024-06-13", "2026-08-18", "2026-08-20"]
        ),
        "security_type": ["Bond", "Bond", "Note", "Note"],
        "original_security_term": ["30-Year", "30-Year", "10-Year", "10-Year"],
        "total_accepted": [1_000.0, 22_711_606_600.0, 30_000_000_000.0, None],
        # Competitive accepted excludes SOMA add-ons; the 2024 auction had none.
        "comp_accepted": [None, 21_967_151_800.0, 30_000_000_000.0, None],
        "soma_accepted": [None, 744_454_800.0, 0.0, None],
        # Bid-to-cover was not published before about 2000 — the 1985 row is a
        # genuine auction with unreported results, not a scheduled one.
        "bid_to_cover_ratio": [None, 2.49, 2.61, None],
        "high_yield": [None, 4.4030, 4.1000, None],
        "avg_med_yield": [None, 4.3500, 4.0800, None],
        "allocation_pctage": [None, 8.49, 51.2, None],
        "primary_dealer_accepted": [None, 3_009_118_500.0, 6_000_000_000.0, None],
        "indirect_bidder_accepted": [None, 15_047_133_300.0, 20_000_000_000.0, None],
        "direct_bidder_accepted": [None, 3_910_900_000.0, 4_000_000_000.0, None],
    })


AS_OF = pd.Timestamp("2026-08-18")


def test_only_genuinely_unheld_auctions_are_dropped():
    """Dropping on a null bid-to-cover discards 3,215 real pre-2000 auctions.

    It looks tidy — the remaining series is clean and simply starts in 1994 — which
    is exactly why the test is on the date instead.
    """
    out = normalize_auctions(auction_rows(), retrieval_date=AS_OF)

    assert len(out) == 3                                  # only the future one goes
    assert out.attrs["n_unheld_dropped"] == 1
    assert out["auction_date"].min() == pd.Timestamp("1985-03-01")


def test_held_auctions_without_published_results_are_kept_and_flagged():
    out = normalize_auctions(auction_rows(), retrieval_date=AS_OF).set_index("auction_date")

    assert not out.loc["1985-03-01", "has_results"]
    assert out.loc["2024-06-13", "has_results"]
    assert out.attrs["n_without_results"] == 1


def test_dispersion_uses_the_published_median():
    """Deviation D3: the median is published, so no constant-maturity proxy is needed."""
    out = normalize_auctions(auction_rows(), retrieval_date=AS_OF).set_index("auction_date")

    # 4.4030 - 4.3500 = 0.0530 percent = 5.30 bps
    assert out.loc["2024-06-13", "dispersion_bps"] == pytest.approx(5.30)
    assert out.loc["2024-06-13", "tail_proxy_method"] == "high_minus_published_median"


def test_dispersion_is_unavailable_where_yields_are_not_published():
    out = normalize_auctions(auction_rows(), retrieval_date=AS_OF).set_index("auction_date")
    assert pd.isna(out.loc["1985-03-01", "dispersion_bps"])
    assert out.loc["1985-03-01", "tail_proxy_method"] == "unavailable"


def test_bidder_shares_use_the_competitive_base_not_the_total():
    """`total_accepted` includes SOMA add-ons, which reached 37% of an auction in 2021.

    Dividing by the total depresses dealer and indirect shares in exactly the QE
    years, feeding a central-bank artefact into the stress score as if it were
    weakening private demand. On the competitive base the three classes sum to 1.
    """
    out = normalize_auctions(auction_rows(), retrieval_date=AS_OF).set_index("auction_date")
    row = out.loc["2024-06-13"]

    assert row["indirect_pct"] == pytest.approx(15_047_133_300 / 21_967_151_800)
    total = row["indirect_pct"] + row["primary_dealer_pct"] + row["direct_pct"]
    assert total == pytest.approx(1.0, abs=1e-4)
    assert row["bidder_share_basis"] == "competitive"


def test_missing_competitive_figure_falls_back_and_is_recorded():
    rows = auction_rows()
    rows.loc[2, "comp_accepted"] = None
    out = normalize_auctions(rows, retrieval_date=AS_OF).set_index("auction_date")

    assert out.loc["2026-08-18", "bidder_share_basis"] == "total_accepted"


# --------------------------------------------------------------------------- #
# subtotal labels and the WAM input check
# --------------------------------------------------------------------------- #

from src.transformation.normalize import (  # noqa: E402
    extract_subtotals,
    normalize_securities_detail,
    parse_subtotal_label,
    unclassified_subtotal_rows,
)
from src.validation.reconciliation import (  # noqa: E402
    reconcile_detail_to_published_subtotal,
)


def test_frn_is_classified_before_notes():
    """"Floating Rate Notes" contains "Notes", so order decides the answer."""
    assert parse_subtotal_label("Total Unmatured Treasury Floating Rate Notes") == (
        "unmatured", "FRN",
    )
    assert parse_subtotal_label("Total Unmatured Treasury Notes") == ("unmatured", "NOTES")


def test_unmatured_is_classified_before_matured():
    """"Unmatured" contains "Matured" — the wrong order silently swaps the two."""
    assert parse_subtotal_label("Total Unmatured Treasury Bills") == ("unmatured", "BILLS")
    assert parse_subtotal_label("Total Matured Treasury Bills") == ("matured", "BILLS")


def test_source_label_variants_all_parse():
    """Treasury's own labels are not stable, including one outright typo."""
    assert parse_subtotal_label("Total Tresasury Floating Rate Notes") == ("total", "FRN")
    assert parse_subtotal_label("Total Unmatured Treasury Floating Rate Notes.") == (
        "unmatured", "FRN",
    )
    assert parse_subtotal_label("Treasury Floating Rate Notes") == ("unmatured", "FRN")
    assert parse_subtotal_label("Matured Treasury Floating Rate Notes") == ("matured", "FRN")


def test_tips_renames_all_map_to_tips():
    for label in (
        "Total Treasury Inflation-Indexed Notes",
        "Total Treasury Inflation-Indexed Bonds",
        "Total Treasury Inflation-Protected Securities",
        "Total Treasury TIPS",
    ):
        assert parse_subtotal_label(label) == ("total", "TIPS")


def test_a_bare_cusip_is_not_a_subtotal():
    """Observed once in the source: a security whose maturity date is missing."""
    assert parse_subtotal_label("9127950") is None
    assert parse_subtotal_label(None) is None
    assert parse_subtotal_label("nan") is None


def detail_and_subtotals():
    typed = pd.DataFrame({
        "record_date": pd.to_datetime(["2024-06-30"] * 4),
        "security_class1_desc": ["Notes", "Notes", "Notes", "Notes"],
        "security_class2_desc": ["912828AA1", "912828BB2",
                                 "Total Unmatured Treasury Notes",
                                 "Total Matured Treasury Notes"],
        "maturity_date": pd.to_datetime(["2030-01-31", "2031-01-31", None, None]),
        "issue_date": pd.to_datetime(["2020-01-31", "2021-01-31", None, None]),
        "outstanding_amt": [100.0, 50.0, 150.0, 7.0],
        "inflation_adj_amt": [0.0, 0.0, 0.0, 0.0],
        "interest_rate_pct": [2.0, 2.5, None, None],
    })
    return typed


def test_detail_reconciles_to_the_published_unmatured_subtotal():
    typed = detail_and_subtotals()
    securities = normalize_securities_detail(typed)
    result = reconcile_detail_to_published_subtotal(
        securities, extract_subtotals(typed), tolerance_pct=0.1
    )
    assert result.ok
    assert result.n_periods == 1


def test_check_is_against_unmatured_not_the_class_total():
    """Matured-but-unredeemed debt sits inside the class total but carries no duration.

    Checking against the class total would fail for a legitimate reason — for FRNs
    in 2023-04 that was $85bn on $601bn — and hide any real break behind it.
    """
    typed = detail_and_subtotals()
    subtotals = extract_subtotals(typed)
    unmatured = subtotals[subtotals["kind"] == "unmatured"]["amount"].iloc[0]
    total = subtotals[subtotals["kind"] == "matured"]["amount"].iloc[0] + unmatured

    assert unmatured == pytest.approx(150.0 * MILLIONS)
    assert total == pytest.approx(157.0 * MILLIONS)


def test_a_real_break_still_fails():
    typed = detail_and_subtotals()
    typed.loc[0, "outstanding_amt"] = 10.0          # detail no longer sums to 150
    securities = normalize_securities_detail(typed)
    result = reconcile_detail_to_published_subtotal(
        securities, extract_subtotals(typed), tolerance_pct=0.1
    )
    assert not result.ok


def test_a_known_source_defect_is_excluded_by_exact_key():
    """Excluded by (date, class), never by loosening the tolerance for everyone."""
    typed = detail_and_subtotals()
    typed.loc[0, "outstanding_amt"] = 10.0
    securities = normalize_securities_detail(typed)
    subtotals = extract_subtotals(typed)

    result = reconcile_detail_to_published_subtotal(
        securities, subtotals, tolerance_pct=0.1,
        known_defects=[{"observation_date": "2024-06-30", "security_class": "NOTES"}],
    )
    assert result.ok

    wrong_class = reconcile_detail_to_published_subtotal(
        securities, subtotals, tolerance_pct=0.1,
        known_defects=[{"observation_date": "2024-06-30", "security_class": "BILLS"}],
    )
    assert not wrong_class.ok


def test_rows_with_no_maturity_and_no_label_are_surfaced():
    typed = detail_and_subtotals()
    typed.loc[2, "security_class2_desc"] = "9127950"     # a CUSIP where a label belongs
    orphans = unclassified_subtotal_rows(typed)
    assert len(orphans) == 1


# --------------------------------------------------------------------------- #
# Buybacks
# --------------------------------------------------------------------------- #

def _ops(rows):
    base = {"operation_date": "2026-08-20", "settlement_date": "2026-08-21",
            "operation_type": "Liquidity Support", "security_type": "Nominal Coupons",
            "maturity_bucket": "3Y to 5Y", "total_par_amt_offered": 10e9,
            "total_par_amt_accepted": 2e9, "max_par_amt_redeemed": 4e9}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_buyback_classes_map_and_unknown_types_raise():
    out = normalize_buybacks(_ops([{}, {"security_type": "TIPS"}]))
    assert list(out.security_class.astype(str)) == ["COUPONS", "TIPS"]
    with pytest.raises(NormalizationError):
        normalize_buybacks(_ops([{"security_type": "Corporate Bonds"}]))


def test_the_2000_era_null_type_is_assumed_coupons_and_flagged():
    """The 2000-02 program carries no security type. It bought back long bonds,
    so COUPONS is right — but it is an assumption and must travel on the row."""
    out = normalize_buybacks(_ops([{"security_type": None}]))
    assert str(out.security_class.iloc[0]) == "COUPONS"
    assert bool(out.class_assumed.iloc[0])
    stated = normalize_buybacks(_ops([{}]))
    assert not bool(stated.class_assumed.iloc[0])


def test_monthly_buyback_par_fills_gaps_with_zero_not_nan():
    """A month with no operation is a true zero — Treasury retired nothing.
    NaN would poison the adjusted coupon flow for most of history."""
    ops = normalize_buybacks(_ops([
        {"operation_date": "2024-05-10", "total_par_amt_accepted": 2e9},
        {"operation_date": "2024-08-20", "total_par_amt_accepted": 3e9},
    ]))
    par = monthly_buyback_par(ops)
    assert par[pd.Period("2024-06", freq="M")] == 0.0
    assert par[pd.Period("2024-05", freq="M")] == 2e9
    assert len(par) == 4


def test_monthly_buyback_par_is_per_class():
    ops = normalize_buybacks(_ops([
        {"total_par_amt_accepted": 2e9},
        {"security_type": "TIPS", "total_par_amt_accepted": 5e8},
    ]))
    assert monthly_buyback_par(ops).iloc[0] == 2e9
    assert monthly_buyback_par(ops, security_class="TIPS").iloc[0] == 5e8


def test_negative_par_accepted_is_refused():
    with pytest.raises(NormalizationError):
        normalize_buybacks(_ops([{"total_par_amt_accepted": -1.0}]))
