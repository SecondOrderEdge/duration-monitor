"""Tests for bill share, net issuance and the funding ratios.

The gap tests matter most here: a missing month must produce NaN, never a change
measured across the gap and reported as if it were a normal period.
"""

import numpy as np
import pandas as pd
import pytest

from src.calculations.issuance import (
    bill_share,
    bill_share_changes,
    bill_to_coupon_ratio,
    incremental_bill_funding,
    net_issuance,
)


def _long(rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["observation_date", "security_class", "amount_outstanding"])


@pytest.fixture
def three_months() -> pd.DataFrame:
    return _long(
        [
            ("2024-01-31", "BILLS", 200.0),
            ("2024-01-31", "NOTES", 500.0),
            ("2024-01-31", "BONDS", 300.0),
            ("2024-01-31", "TOTAL_MARKETABLE", 1000.0),
            ("2024-02-29", "BILLS", 250.0),
            ("2024-02-29", "NOTES", 510.0),
            ("2024-02-29", "BONDS", 300.0),
            ("2024-02-29", "TOTAL_MARKETABLE", 1060.0),
            ("2024-03-31", "BILLS", 260.0),
            ("2024-03-31", "NOTES", 520.0),
            ("2024-03-31", "BONDS", 300.0),
            ("2024-03-31", "TOTAL_MARKETABLE", 1080.0),
        ]
    )


class TestBillShare:
    def test_uses_published_total_not_the_sum_of_parts(self, three_months):
        """Components sum to 1000/1060/1080 here, but the published total governs.

        Making the two disagree proves which one the calculation used.
        """
        df = three_months.copy()
        df.loc[df["security_class"] == "TOTAL_MARKETABLE", "amount_outstanding"] = [
            2000.0,
            2000.0,
            2000.0,
        ]
        share = bill_share(df)
        assert share.iloc[0] == pytest.approx(200 / 2000)

    def test_hand_computed_shares(self, three_months):
        share = bill_share(three_months)
        np.testing.assert_allclose(
            share.to_numpy(), [200 / 1000, 250 / 1060, 260 / 1080]
        )

    def test_missing_total_row_raises(self, three_months):
        df = three_months[three_months["security_class"] != "TOTAL_MARKETABLE"]
        with pytest.raises(ValueError, match="TOTAL_MARKETABLE"):
            bill_share(df)

    def test_missing_bills_row_raises(self, three_months):
        df = three_months[three_months["security_class"] != "BILLS"]
        with pytest.raises(ValueError, match="BILLS"):
            bill_share(df)

    def test_zero_total_yields_nan(self):
        df = _long(
            [("2024-01-31", "BILLS", 0.0), ("2024-01-31", "TOTAL_MARKETABLE", 0.0)]
        )
        assert np.isnan(bill_share(df).iloc[0])

    def test_missing_month_becomes_nan_rather_than_being_closed_up(self):
        """January and March present, February absent."""
        df = _long(
            [
                ("2024-01-31", "BILLS", 200.0),
                ("2024-01-31", "TOTAL_MARKETABLE", 1000.0),
                ("2024-03-31", "BILLS", 260.0),
                ("2024-03-31", "TOTAL_MARKETABLE", 1080.0),
            ]
        )
        share = bill_share(df)
        assert len(share) == 3
        assert np.isnan(share.iloc[1])


class TestPivotSafety:
    """Regression tests for two silent-failure modes in the wide reshape.

    Both were live bugs: `pivot_table(aggfunc="sum")` converts a missing
    observation to 0.0 and silently sums duplicate keys.
    """

    def test_missing_observation_is_not_converted_to_zero(self):
        """NOTES absent in February must stay NaN, not become a zero delta."""
        df = _long(
            [
                ("2024-01-31", "BILLS", 100.0),
                ("2024-01-31", "NOTES", 100.0),
                ("2024-02-29", "BILLS", 200.0),
                ("2024-03-31", "BILLS", 300.0),
                ("2024-03-31", "NOTES", 140.0),
            ]
        )
        net = net_issuance(df)
        notes = net[net["security_class"] == "NOTES"].set_index("period")["net_issuance"]

        # February has no NOTES observation at all.
        assert np.isnan(notes.iloc[1])
        # March cannot be measured against a missing February either.
        assert np.isnan(notes.iloc[2])

    def test_duplicate_keys_raise_rather_than_being_summed(self):
        """Two countries in one frame would otherwise be added together."""
        df = _long(
            [
                ("2024-01-31", "BILLS", 100.0),
                ("2024-01-31", "BILLS", 250.0),  # e.g. a second country
                ("2024-01-31", "TOTAL_MARKETABLE", 1000.0),
            ]
        )
        with pytest.raises(ValueError, match="duplicate .* keys"):
            bill_share(df)


class TestBillShareChanges:
    def test_change_is_measured_between_endpoints_not_across_rows(self):
        """February missing, but Apr-minus-Jan is still a true 3-month change.

        Both endpoints are present, so the gap between them is irrelevant. What
        would be wrong is closing the gap up and calling Apr-minus-Jan a *two*-row
        change — which is exactly what a naive `.diff()` on the raw rows does.
        """
        df = _long(
            [
                ("2024-01-31", "BILLS", 200.0),
                ("2024-01-31", "TOTAL_MARKETABLE", 1000.0),
                ("2024-03-31", "BILLS", 260.0),
                ("2024-03-31", "TOTAL_MARKETABLE", 1080.0),
                ("2024-04-30", "BILLS", 270.0),
                ("2024-04-30", "TOTAL_MARKETABLE", 1090.0),
            ]
        )
        changes = bill_share_changes(bill_share(df), horizons=(2, 3))

        assert changes["change_3m"].iloc[3] == pytest.approx(270 / 1090 - 200 / 1000)
        # The 2-month change into April lands on the missing February.
        assert np.isnan(changes["change_2m"].iloc[3])

    def test_change_landing_on_a_missing_endpoint_is_nan(self):
        """February missing: the 3-month change into May has no starting point."""
        df = _long(
            [
                ("2024-01-31", "BILLS", 200.0),
                ("2024-01-31", "TOTAL_MARKETABLE", 1000.0),
                ("2024-03-31", "BILLS", 260.0),
                ("2024-03-31", "TOTAL_MARKETABLE", 1080.0),
                ("2024-05-31", "BILLS", 280.0),
                ("2024-05-31", "TOTAL_MARKETABLE", 1100.0),
            ]
        )
        changes = bill_share_changes(bill_share(df), horizons=(3,))
        assert np.isnan(changes["change_3m"].iloc[4])

    def test_change_is_computed_where_history_is_complete(self, three_months):
        changes = bill_share_changes(bill_share(three_months), horizons=(2,))
        expected = 260 / 1080 - 200 / 1000
        assert changes["change_2m"].iloc[2] == pytest.approx(expected)


class TestNetIssuance:
    def test_deltas_are_month_over_month(self, three_months):
        net = net_issuance(three_months)
        bills = net[net["security_class"] == "BILLS"].set_index("period")["net_issuance"]

        assert np.isnan(bills.iloc[0])  # no prior month
        assert bills.iloc[1] == pytest.approx(50.0)
        assert bills.iloc[2] == pytest.approx(10.0)

    def test_delta_across_a_missing_month_is_nan(self):
        df = _long(
            [
                ("2024-01-31", "BILLS", 200.0),
                ("2024-03-31", "BILLS", 260.0),
                ("2024-04-30", "BILLS", 270.0),
            ]
        )
        net = net_issuance(df)
        bills = net[net["security_class"] == "BILLS"].set_index("period")["net_issuance"]

        assert np.isnan(bills.iloc[1])  # February itself
        assert np.isnan(bills.iloc[2])  # March, measured against a missing February
        assert bills.iloc[3] == pytest.approx(10.0)  # April against a present March

    def test_method_is_recorded_on_every_row(self, three_months):
        net = net_issuance(three_months)
        assert (net["method"] == "mspd_delta").all()


class TestIncrementalBillFunding:
    def test_hand_computed_share(self, three_months):
        """February: bills +50, notes +10, bonds 0 -> 50 / 60."""
        result = incremental_bill_funding(
            net_issuance(three_months), min_abs_denominator=1.0
        )
        assert result["incremental_bill_funding"].iloc[1] == pytest.approx(50 / 60)
        assert not result["denominator_masked"].iloc[1]

    def test_small_denominator_is_masked(self):
        """Bills +100 against coupons -95: net borrowing of 5 is not a denominator."""
        df = _long(
            [
                ("2024-01-31", "BILLS", 100.0),
                ("2024-01-31", "NOTES", 100.0),
                ("2024-02-29", "BILLS", 200.0),
                ("2024-02-29", "NOTES", 5.0),
            ]
        )
        result = incremental_bill_funding(net_issuance(df), min_abs_denominator=10.0)

        assert result["net_total"].iloc[1] == pytest.approx(5.0)
        assert np.isnan(result["incremental_bill_funding"].iloc[1])
        assert result["denominator_masked"].iloc[1]

    def test_denominator_just_above_the_floor_is_published(self):
        df = _long(
            [
                ("2024-01-31", "BILLS", 100.0),
                ("2024-01-31", "NOTES", 100.0),
                ("2024-02-29", "BILLS", 200.0),
                ("2024-02-29", "NOTES", 11.0),
            ]
        )
        result = incremental_bill_funding(net_issuance(df), min_abs_denominator=10.0)
        assert result["net_total"].iloc[1] == pytest.approx(11.0)
        assert result["incremental_bill_funding"].iloc[1] == pytest.approx(100 / 11)

    def test_tips_are_excluded_from_coupons_by_default(self):
        """TIPS deltas carry inflation accretion and must not enter the denominator.

        Here TIPS 'grow' by 500 with no issuance; including them would put the
        ratio at 100/600 instead of the correct 100/200.
        """
        df = _long(
            [
                ("2024-01-31", "BILLS", 100.0),
                ("2024-01-31", "NOTES", 100.0),
                ("2024-01-31", "TIPS", 1000.0),
                ("2024-02-29", "BILLS", 200.0),
                ("2024-02-29", "NOTES", 200.0),
                ("2024-02-29", "TIPS", 1500.0),
            ]
        )
        result = incremental_bill_funding(net_issuance(df), min_abs_denominator=1.0)

        assert result["net_total"].iloc[1] == pytest.approx(200.0)
        assert result["incremental_bill_funding"].iloc[1] == pytest.approx(0.5)
        assert "TIPS" not in result["coupon_classes"].iloc[1]

    def test_class_that_never_existed_is_excluded_not_treated_as_a_gap(self):
        """FRNs did not exist before 2014; requiring them would void that history.

        A class with no observation anywhere in the data is structurally absent
        and simply does not participate in the aggregate.
        """
        df = _long(
            [
                ("2024-01-31", "BILLS", 100.0),
                ("2024-01-31", "NOTES", 100.0),
                ("2024-02-29", "BILLS", 200.0),
                ("2024-02-29", "NOTES", 200.0),
            ]
        )
        result = incremental_bill_funding(
            net_issuance(df),
            coupon_classes=("NOTES", "FRN"),  # FRN never appears in the data
            min_abs_denominator=1.0,
        )
        assert result["net_total"].iloc[1] == pytest.approx(200.0)
        assert result["incremental_bill_funding"].iloc[1] == pytest.approx(0.5)

    def test_class_that_starts_reporting_then_goes_missing_is_a_gap(self):
        """Once a class is active, a missing observation voids the aggregate.

        FRN reports in February and March, then disappears in April. April is a
        real gap, not a return to structural absence, so the sum is suppressed
        rather than quietly computed without it.
        """
        df = _long(
            [
                ("2024-01-31", "BILLS", 100.0),
                ("2024-01-31", "NOTES", 100.0),
                ("2024-02-29", "BILLS", 200.0),
                ("2024-02-29", "NOTES", 200.0),
                ("2024-02-29", "FRN", 50.0),
                ("2024-03-31", "BILLS", 300.0),
                ("2024-03-31", "NOTES", 300.0),
                ("2024-03-31", "FRN", 80.0),
                ("2024-04-30", "BILLS", 400.0),
                ("2024-04-30", "NOTES", 400.0),
            ]
        )
        result = incremental_bill_funding(
            net_issuance(df), coupon_classes=("NOTES", "FRN"), min_abs_denominator=1.0
        )

        # March: notes +100, FRN +30 -> both active and present.
        assert result["net_total"].iloc[2] == pytest.approx(100 + 130)
        # April: FRN is active but absent -> genuine gap.
        assert np.isnan(result["net_total"].iloc[3])
        assert result["denominator_masked"].iloc[3]

    def test_non_positive_floor_is_rejected(self, three_months):
        with pytest.raises(ValueError, match="must be positive"):
            incremental_bill_funding(net_issuance(three_months), min_abs_denominator=0.0)


class TestBillToCouponRatio:
    def test_hand_computed_ratio(self, three_months):
        result = bill_to_coupon_ratio(net_issuance(three_months), min_abs_denominator=1.0)
        assert result["bill_to_coupon_ratio"].iloc[1] == pytest.approx(50 / 10)

    def test_negative_coupon_issuance_keeps_its_sign(self):
        """Bills up while coupons shrink is the configuration of interest, not an error."""
        df = _long(
            [
                ("2024-01-31", "BILLS", 100.0),
                ("2024-01-31", "NOTES", 100.0),
                ("2024-02-29", "BILLS", 200.0),
                ("2024-02-29", "NOTES", 50.0),
            ]
        )
        result = bill_to_coupon_ratio(net_issuance(df), min_abs_denominator=10.0)
        assert result["bill_to_coupon_ratio"].iloc[1] == pytest.approx(100 / -50)

    def test_small_coupon_denominator_is_masked(self):
        df = _long(
            [
                ("2024-01-31", "BILLS", 100.0),
                ("2024-01-31", "NOTES", 100.0),
                ("2024-02-29", "BILLS", 200.0),
                ("2024-02-29", "NOTES", 101.0),
            ]
        )
        result = bill_to_coupon_ratio(net_issuance(df), min_abs_denominator=10.0)
        assert np.isnan(result["bill_to_coupon_ratio"].iloc[1])
        assert result["denominator_masked"].iloc[1]


def test_bill_share_reads_a_quarterly_series_as_quarterly():
    """`freq` is explicit: inferring it would read a quarterly gap as monthly gaps."""
    dates = pd.PeriodIndex(["2024Q1", "2024Q2", "2024Q3"], freq="Q").to_timestamp(how="end")
    rows = []
    for d in dates:
        rows.append({"observation_date": d, "security_class": "BILLS",
                     "amount_outstanding": 100.0})
        rows.append({"observation_date": d, "security_class": "TOTAL_MARKETABLE",
                     "amount_outstanding": 1000.0})
    share = bill_share(pd.DataFrame(rows), freq="Q")
    assert share.index.freqstr.startswith("Q")
    assert len(share) == 3
    assert (share == 0.1).all()


def test_buyback_addback_undoes_the_retirement_in_the_funding_ratio():
    """A $20bn coupon buyback must not read as coupon restraint.

    Bills +30, coupons -10 of which -20 is buyback retirement: true coupon
    issuance was +10. Unadjusted the ratio reads 30/20 = 1.5 (implausible,
    bill-financed retirement); adjusted it reads 30/40 = 0.75.
    """
    idx = pd.PeriodIndex(["2024-05"], freq="M")
    rows = []
    for cls, amt in (("BILLS", 30e9), ("NOTES", -10e9), ("BONDS", 0.0), ("FRN", 0.0)):
        rows.append({"period": idx[0], "security_class": cls, "net_issuance": amt})
    net = pd.DataFrame(rows)
    addback = pd.Series([20e9], index=idx)
    un = incremental_bill_funding(net, min_abs_denominator=1e9)
    adj = incremental_bill_funding(net, min_abs_denominator=1e9,
                                   coupon_buyback_addback=addback)
    assert un["incremental_bill_funding"].iloc[0] == pytest.approx(1.5)
    assert adj["incremental_bill_funding"].iloc[0] == pytest.approx(0.75)


def test_months_outside_the_addback_span_are_untouched():
    idx = pd.PeriodIndex(["2010-01"], freq="M")
    net = pd.DataFrame([{"period": idx[0], "security_class": c, "net_issuance": v}
                        for c, v in (("BILLS", 10e9), ("NOTES", 30e9),
                                     ("BONDS", 0.0), ("FRN", 0.0))])
    addback = pd.Series([5e9], index=pd.PeriodIndex(["2024-05"], freq="M"))
    un = incremental_bill_funding(net, min_abs_denominator=1e9)
    adj = incremental_bill_funding(net, min_abs_denominator=1e9,
                                   coupon_buyback_addback=addback)
    assert adj["incremental_bill_funding"].iloc[0] == un["incremental_bill_funding"].iloc[0]


def test_a_negative_addback_is_refused():
    idx = pd.PeriodIndex(["2024-05"], freq="M")
    net = pd.DataFrame([{"period": idx[0], "security_class": "BILLS", "net_issuance": 1e9},
                        {"period": idx[0], "security_class": "NOTES", "net_issuance": 1e9}])
    with pytest.raises(ValueError):
        incremental_bill_funding(net, min_abs_denominator=1e8,
                                 coupon_buyback_addback=pd.Series([-1.0], index=idx))
