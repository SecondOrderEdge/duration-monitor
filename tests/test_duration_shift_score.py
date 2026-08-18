"""Tests for the composite score, its weighting, and the cash adjustment.

The weighting is the part with a wrong answer that looks right: equal weights on
six factors, three of which measure the same thing, silently give that one
measurement half the score. These tests pin the properties that stops.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.calculations.issuance import cash_adjusted_bill_funding, net_issuance
from src.signals.duration_shift_score import (
    FACTOR_DIRECTION,
    build_factors,
    classify_regime,
    score_band,
    correlation_weights,
    duration_shift_score,
    expanding_weights,
    percentile_ranks,
)

RNG = np.random.default_rng(0)


def ranks_with_duplicate(n: int = 120) -> pd.DataFrame:
    """Three independent factors, one of which is duplicated twice."""
    idx = pd.period_range("2010-01", periods=n, freq="M")
    a = pd.Series(RNG.normal(size=n), index=idx)
    b = pd.Series(RNG.normal(size=n), index=idx)
    c = pd.Series(RNG.normal(size=n), index=idx)
    return pd.DataFrame({
        "a": a, "a_copy1": a * 2 + 1, "a_copy2": a * 3 - 5,   # perfectly rank-correlated
        "b": b, "c": c,
    })


# --------------------------------------------------------------------------- #
# weighting
# --------------------------------------------------------------------------- #


def test_duplicated_factors_share_weight_instead_of_multiplying_it():
    """Three copies of one factor must not out-weigh two independent ones."""
    w = correlation_weights(ranks_with_duplicate(), ridge=0.5)

    duplicated = w[["a", "a_copy1", "a_copy2"]].sum()
    independent = w[["b", "c"]].sum()

    assert duplicated < independent, (
        f"three copies of one measurement took {duplicated:.2f} of the weight "
        f"against {independent:.2f} for two independent factors"
    )
    assert w["b"] > w["a"]


def test_every_factor_is_retained():
    """The brief's six factors stay six. A duplicate earns less, not nothing."""
    w = correlation_weights(ranks_with_duplicate(), ridge=0.5)
    assert (w > 0).all()
    assert w.sum() == pytest.approx(1.0)


def test_weights_are_equal_when_factors_are_independent():
    idx = pd.period_range("2010-01", periods=200, freq="M")
    independent = pd.DataFrame(
        {name: RNG.normal(size=200) for name in ("a", "b", "c", "d")}, index=idx
    )
    w = correlation_weights(independent, ridge=0.5)
    assert w.max() - w.min() < 0.05


def test_ridge_is_required_to_be_a_proper_fraction():
    ranks = ranks_with_duplicate()
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="ridge"):
            correlation_weights(ranks, ridge=bad)


def test_heavier_shrinkage_moves_weights_toward_equal():
    ranks = ranks_with_duplicate()
    light = correlation_weights(ranks, ridge=0.2)
    heavy = correlation_weights(ranks, ridge=0.9)
    assert (heavy.max() - heavy.min()) < (light.max() - light.min())


# --------------------------------------------------------------------------- #
# expanding window
# --------------------------------------------------------------------------- #


def test_expanding_weights_never_use_future_data():
    """Fitting weights on the full sample leaks the future through the weighting.

    The weight at date t must be reproducible from the history up to t alone.
    """
    ranks = ranks_with_duplicate()
    full = expanding_weights(ranks, ridge=0.5, min_months=36)

    cutoff = ranks.index[80]
    truncated = expanding_weights(ranks.loc[:cutoff], ridge=0.5, min_months=36)

    pd.testing.assert_series_equal(full.loc[cutoff], truncated.loc[cutoff])


def test_weights_fall_back_to_equal_before_enough_history():
    ranks = ranks_with_duplicate()
    weights = expanding_weights(ranks, ridge=0.5, min_months=36)
    early = weights.iloc[10]
    assert early.max() - early.min() == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# the score
# --------------------------------------------------------------------------- #


def test_score_renormalises_over_available_factors():
    """A factor that has not started yet must not drag the score toward zero."""
    idx = pd.period_range("2020-01", periods=6, freq="M")
    ranks = pd.DataFrame(
        {"a": [80.0] * 6, "b": [80.0] * 6, "c": [80.0] * 6,
         "d": [np.nan, np.nan, np.nan, 80.0, 80.0, 80.0]},
        index=idx,
    )
    weights = pd.Series(0.25, index=["a", "b", "c", "d"])
    out = duration_shift_score(ranks, weights, min_factors=3)

    assert out["score"].iloc[0] == pytest.approx(80.0)   # three factors, all 80
    assert out["score"].iloc[-1] == pytest.approx(80.0)  # four factors, all 80


def test_too_few_factors_scores_nan_rather_than_a_partial_composite():
    idx = pd.period_range("2020-01", periods=3, freq="M")
    ranks = pd.DataFrame(
        {"a": [50.0, 50.0, 50.0], "b": [np.nan, np.nan, 60.0],
         "c": [np.nan, np.nan, 60.0], "d": [np.nan, np.nan, 60.0]},
        index=idx,
    )
    out = duration_shift_score(ranks, pd.Series(0.25, index=list("abcd")), min_factors=4)
    assert out["score"].isna().iloc[0]
    assert out["score"].notna().iloc[-1]


def test_contributions_sum_to_the_score():
    """A reading has to be explainable, so contributions must add up."""
    ranks = ranks_with_duplicate().rank(pct=True) * 100
    weights = correlation_weights(ranks, ridge=0.5)
    out = duration_shift_score(ranks, weights, min_factors=3)

    contribs = out[[c for c in out.columns if c.startswith("contrib_")]].sum(axis=1)
    pd.testing.assert_series_equal(
        contribs.dropna(), out["score"].dropna(), check_names=False
    )


def test_percentile_ranks_are_bounded_so_an_outlier_cannot_drag_the_scale():
    """Why crises do not distort the weighting: a rank has nowhere further to go."""
    idx = pd.period_range("2000-01", periods=200, freq="M")
    base = pd.Series(RNG.normal(size=200), index=idx)

    mild = base.copy(); mild.iloc[150] = base.max() * 1.01      # just the new high
    extreme = base.copy(); extreme.iloc[150] = 1e9              # a ten-sigma event

    a = percentile_ranks(pd.DataFrame({"x": mild}), window=120, min_periods=60)
    b = percentile_ranks(pd.DataFrame({"x": extreme}), window=120, min_periods=60)

    # Both are simply "the highest reading so far". How much higher is irrelevant,
    # which is why a crisis cannot drag the scale the way it would in a z-score
    # composite — and why excluding 2008 or 2020 changes the score by under a point.
    pd.testing.assert_frame_equal(a, b)
    assert b["x"].max() <= 100.0


# --------------------------------------------------------------------------- #
# cash adjustment (Deviation D5)
# --------------------------------------------------------------------------- #


def test_cash_rebuild_is_removed_from_both_sides_of_the_ratio():
    """A bill-funded rebuild of the cash balance is not a duration decision."""
    idx = pd.period_range("2023-01", periods=3, freq="M")
    debt = pd.DataFrame({
        "observation_date": list(pd.to_datetime(["2023-01-31", "2023-02-28", "2023-03-31"])) * 2,
        "security_class": ["BILLS"] * 3 + ["NOTES"] * 3,
        "amount_outstanding": [1000.0, 1000.0, 1500.0, 500.0, 500.0, 500.0],
    })
    net = net_issuance(debt)
    # The entire bill increase funds a cash build; nothing financed a deficit.
    cash = pd.Series([100.0, 100.0, 600.0], index=idx, name="tga_balance")

    out = cash_adjusted_bill_funding(net, cash, min_abs_denominator=1.0)
    row = out.loc[idx[2]]

    assert row["net_bills"] == pytest.approx(500.0)
    assert row["delta_cash_balance"] == pytest.approx(500.0)
    assert row["adjusted_net_bills"] == pytest.approx(0.0)
    # Every dollar borrowed rebuilt cash, so there is no deficit-financing
    # borrowing for bills to be a share OF. The ratio is undefined, not zero, and
    # masking it is the same refusal the debt-ceiling guard makes.
    assert row["adjusted_net_borrowing"] == pytest.approx(0.0)
    assert bool(row["denominator_masked"])
    assert pd.isna(row["incremental_bill_funding_adjusted"])


def test_partial_cash_rebuild_lowers_the_ratio_without_masking_it():
    idx = pd.period_range("2023-01", periods=3, freq="M")
    debt = pd.DataFrame({
        "observation_date": list(pd.to_datetime(["2023-01-31", "2023-02-28", "2023-03-31"])) * 2,
        "security_class": ["BILLS"] * 3 + ["NOTES"] * 3,
        "amount_outstanding": [1000.0, 1000.0, 1800.0, 500.0, 500.0, 700.0],
    })
    net = net_issuance(debt)
    cash = pd.Series([100.0, 100.0, 400.0], index=idx)          # 300 of the 1000 rebuilt cash

    out = cash_adjusted_bill_funding(net, cash, min_abs_denominator=1.0)
    row = out.loc[idx[2]]

    unadjusted = row["net_bills"] / row["net_borrowing"]         # 800 / 1000
    assert unadjusted == pytest.approx(0.8)
    # (800 - 300) / (1000 - 300)
    assert row["incremental_bill_funding_adjusted"] == pytest.approx(500 / 700)
    assert not bool(row["denominator_masked"])


def test_cash_adjustment_leaves_a_deficit_funded_month_alone():
    idx = pd.period_range("2024-01", periods=2, freq="M")
    debt = pd.DataFrame({
        "observation_date": list(pd.to_datetime(["2024-01-31", "2024-02-29"])) * 2,
        "security_class": ["BILLS"] * 2 + ["NOTES"] * 2,
        "amount_outstanding": [1000.0, 1400.0, 500.0, 500.0],
    })
    net = net_issuance(debt)
    flat_cash = pd.Series([100.0, 100.0], index=idx)

    out = cash_adjusted_bill_funding(net, flat_cash, min_abs_denominator=1.0)
    assert out["incremental_bill_funding_adjusted"].iloc[-1] == pytest.approx(1.0)



# --------------------------------------------------------------------------- #
# factor directions
# --------------------------------------------------------------------------- #


def test_coupon_restraint_direction_is_inverted():
    """`build_factors` computes the coupon SHARE of need, so high means NOT restraint.

    This is a regression guard for a sign error that broke nothing visibly: the
    score stayed in range, the series still looked plausible, and the only
    symptom was that the 2020 spike the brief says MUST appear flattened from
    +17.5 points to +3.3.
    """
    assert FACTOR_DIRECTION["coupon_restraint"] == -1
    assert FACTOR_DIRECTION["wam_trend"] == -1
    assert FACTOR_DIRECTION["bill_share_trend"] == +1


def test_higher_coupon_share_lowers_the_score_factor():
    idx = pd.period_range("2020-01", periods=14, freq="M")
    flat = pd.Series(1.0, index=idx)
    net = pd.DataFrame({
        "period": list(idx) * 2,
        "security_class": ["BILLS"] * 14 + ["NOTES"] * 14,
        "net_issuance": [100.0] * 14 + [900.0] * 14,     # coupons dominate
        "method": ["mspd_delta"] * 28,
    })
    heavy_coupons = build_factors(
        bill_share_series=flat, net=net, incremental_funding=flat, wam_years=flat,
        term_premium_10y=flat, auction_stress=flat,
        coupon_classes=("NOTES",), min_abs_denominator=1.0,
    )["coupon_restraint"].dropna()

    net_light = net.copy()
    net_light.loc[net_light.security_class == "NOTES", "net_issuance"] = 100.0
    light_coupons = build_factors(
        bill_share_series=flat, net=net_light, incremental_funding=flat, wam_years=flat,
        term_premium_10y=flat, auction_stress=flat,
        coupon_classes=("NOTES",), min_abs_denominator=1.0,
    )["coupon_restraint"].dropna()

    # Restrained coupons must score HIGHER than coupons that kept pace.
    assert light_coupons.iloc[-1] > heavy_coupons.iloc[-1]


def test_regime_conditions_naming_an_absent_input_raise():
    """Silently skipping a condition would promote a regime by dropping a test."""
    inputs = pd.DataFrame({"duration_shift_score": [90.0]})
    regimes = {"red": {"duration_shift_score_at_least": 80,
                       "long_end_auction_stress_at_least": 25}}
    with pytest.raises(ValueError, match="long_end_auction_stress"):
        classify_regime(inputs, regimes)


def test_score_bands_are_half_open_so_a_boundary_lands_upward():
    bands = [{"name": "neutral", "from": 40, "to": 60},
             {"name": "meaningful shortening", "from": 60, "to": 80}]
    out = score_band(pd.Series([59.9, 60.0, 79.9]), bands)
    assert list(out) == ["neutral", "meaningful shortening", "meaningful shortening"]
