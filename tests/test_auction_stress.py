"""Tests for the auction stress score.

The sign convention is the thing most likely to be silently wrong — a flipped sign
produces a plausible-looking series that says the opposite of the truth — so it is
tested per component against a hand-computed z-score.
"""

import numpy as np
import pandas as pd
import pytest

from src.signals.auction_stress import (
    Component,
    auction_stress_score,
    component_zscores,
    long_end_stress,
)

# Twelve trailing auctions alternating 2.4 / 2.6:
#   mean = 2.5
#   sample variance = 12 * 0.01 / 11 = 0.010909090...
#   sd = 0.1044466...
TRAILING_BTC = [2.4, 2.6] * 6
TRAILING_MEAN = 2.5
TRAILING_SD = np.std(TRAILING_BTC, ddof=1)


def _auctions(btc_values, term="10Y", **extra) -> pd.DataFrame:
    n = len(btc_values)
    data = {
        "auction_date": pd.date_range("2023-01-01", periods=n, freq="ME"),
        "term": [term] * n,
        "bid_to_cover": btc_values,
    }
    for key, value in extra.items():
        data[key] = value
    return pd.DataFrame(data)


def test_trailing_sd_underlying_the_fixture():
    """Guard the fixture's own arithmetic."""
    assert TRAILING_SD == pytest.approx(np.sqrt(12 * 0.01 / 11))


class TestSignConvention:
    def test_low_bid_to_cover_scores_as_weak(self):
        """A 13th auction at 2.3 is below the trailing mean, so stress is positive.

        z = (2.3 - 2.5) / 0.1044466 = -1.9149...
        stress contribution = -1 * z = +1.9149...
        score = 1.9149 / 3 * 100 = 63.83
        """
        df = _auctions(TRAILING_BTC + [2.3])
        components = {"btc": Component("bid_to_cover", sign=-1, weight=1.0)}

        result = auction_stress_score(df, components=components, min_components=1)
        expected_z = (2.3 - TRAILING_MEAN) / TRAILING_SD

        assert expected_z == pytest.approx(-1.9149, abs=1e-4)
        assert result["stress_z"].iloc[-1] == pytest.approx(-expected_z)
        assert result["stress_score"].iloc[-1] == pytest.approx(-expected_z / 3 * 100)
        assert result["stress_score"].iloc[-1] > 0  # weak

    def test_high_bid_to_cover_scores_as_strong(self):
        df = _auctions(TRAILING_BTC + [2.7])
        components = {"btc": Component("bid_to_cover", sign=-1, weight=1.0)}
        result = auction_stress_score(df, components=components, min_components=1)
        assert result["stress_score"].iloc[-1] < 0  # strong

    def test_high_dealer_takedown_scores_as_weak(self):
        """Dealers are the residual buyer: taking more means others took less."""
        dealer = [20.0, 22.0] * 6 + [30.0]
        df = _auctions([2.5] * 13, primary_dealer_pct=dealer)
        components = {"dealer": Component("primary_dealer_pct", sign=+1, weight=1.0)}
        result = auction_stress_score(df, components=components, min_components=1)
        assert result["stress_score"].iloc[-1] > 0

    def test_low_indirect_participation_scores_as_weak(self):
        indirect = [60.0, 62.0] * 6 + [50.0]
        df = _auctions([2.5] * 13, indirect_pct=indirect)
        components = {"indirect": Component("indirect_pct", sign=-1, weight=1.0)}
        result = auction_stress_score(df, components=components, min_components=1)
        assert result["stress_score"].iloc[-1] > 0


class TestInsufficientHistory:
    def test_fewer_than_twelve_trailing_auctions_scores_nan(self):
        """A partial window is not a smaller window; it is no score at all."""
        df = _auctions([2.4, 2.6, 2.5, 2.4])
        components = {"btc": Component("bid_to_cover", sign=-1, weight=1.0)}
        result = auction_stress_score(df, components=components, min_components=1)
        assert result["stress_score"].isna().all()

    def test_tenors_are_scored_independently(self):
        """A 30Y auction must not be judged against 10Y history."""
        ten = _auctions(TRAILING_BTC + [2.3], term="10Y")
        thirty = _auctions([2.0, 2.1], term="30Y")
        df = pd.concat([ten, thirty], ignore_index=True)

        components = {"btc": Component("bid_to_cover", sign=-1, weight=1.0)}
        result = auction_stress_score(df, components=components, min_components=1)

        scored_30y = result[result["term"] == "30Y"]["stress_score"]
        assert scored_30y.isna().all()  # only two 30Y auctions exist
        assert result[result["term"] == "10Y"]["stress_score"].iloc[-1] > 0


class TestComposite:
    def test_missing_component_column_is_absent_not_zero(self):
        """A feed that lacks a column must not contribute a neutral zero z-score."""
        df = _auctions(TRAILING_BTC + [2.3])  # no indirect_pct column at all
        components = {
            "btc": Component("bid_to_cover", sign=-1, weight=1.0),
            "indirect": Component("indirect_pct", sign=-1, weight=1.0),
        }
        result = auction_stress_score(df, components=components, min_components=1)

        assert result["z_indirect"].isna().all()
        assert result["n_components"].iloc[-1] == 1
        # Renormalised over the one available component, not halved toward zero.
        expected_z = (2.3 - TRAILING_MEAN) / TRAILING_SD
        assert result["stress_z"].iloc[-1] == pytest.approx(-expected_z)

    def test_min_components_suppresses_a_one_legged_composite(self):
        df = _auctions(TRAILING_BTC + [2.3])
        components = {
            "btc": Component("bid_to_cover", sign=-1, weight=1.0),
            "indirect": Component("indirect_pct", sign=-1, weight=1.0),
        }
        result = auction_stress_score(df, components=components, min_components=2)
        assert result["stress_score"].isna().all()

    def test_zero_weight_component_is_excluded_but_still_computed(self):
        """The default tail proxy is a diagnostic: reported, not scored (D3)."""
        tail = [1.0, 2.0] * 6 + [15.0]
        df = _auctions(TRAILING_BTC + [2.3], tail_proxy_bps=tail)
        components = {
            "btc": Component("bid_to_cover", sign=-1, weight=1.0),
            "tail": Component("tail_proxy_bps", sign=+1, weight=0.0),
        }
        result = auction_stress_score(df, components=components, min_components=1)

        assert result["z_tail"].notna().iloc[-1]  # diagnostic is available
        assert "tail" not in result["components_used"].iloc[-1]  # but not scored
        expected_z = (2.3 - TRAILING_MEAN) / TRAILING_SD
        assert result["stress_z"].iloc[-1] == pytest.approx(-expected_z)

    def test_weights_are_applied(self):
        dealer = [20.0, 22.0] * 6 + [30.0]
        df = _auctions(TRAILING_BTC + [2.3], primary_dealer_pct=dealer)

        equal = auction_stress_score(
            df,
            components={
                "btc": Component("bid_to_cover", -1, 1.0),
                "dealer": Component("primary_dealer_pct", +1, 1.0),
            },
            min_components=2,
        )["stress_z"].iloc[-1]

        btc_heavy = auction_stress_score(
            df,
            components={
                "btc": Component("bid_to_cover", -1, 3.0),
                "dealer": Component("primary_dealer_pct", +1, 1.0),
            },
            min_components=2,
        )["stress_z"].iloc[-1]

        assert equal != pytest.approx(btc_heavy)

    def test_score_is_clipped_and_the_clip_is_flagged(self):
        """An extreme auction saturates the axis, and says so."""
        df = _auctions(TRAILING_BTC + [1.0])
        components = {"btc": Component("bid_to_cover", sign=-1, weight=1.0)}
        result = auction_stress_score(df, components=components, min_components=1)

        assert result["stress_score"].iloc[-1] == pytest.approx(100.0)
        assert bool(result["score_clipped"].iloc[-1])

    def test_all_zero_weights_is_rejected(self):
        df = _auctions(TRAILING_BTC + [2.3])
        with pytest.raises(ValueError, match="non-zero weight"):
            auction_stress_score(
                df, components={"btc": Component("bid_to_cover", -1, 0.0)}
            )

    def test_missing_tenor_column_is_rejected(self):
        df = _auctions(TRAILING_BTC + [2.3]).drop(columns=["term"])
        with pytest.raises(ValueError, match="missing required column"):
            component_zscores(df)


class TestLongEndStress:
    def test_averages_only_long_end_tenors(self):
        long_end = _auctions(TRAILING_BTC + [2.3], term="30Y")
        short = _auctions(TRAILING_BTC + [2.9], term="2Y")
        df = pd.concat([long_end, short], ignore_index=True)

        components = {"btc": Component("bid_to_cover", sign=-1, weight=1.0)}
        scored = auction_stress_score(df, components=components, min_components=1)
        result = long_end_stress(scored, min_auctions=1, window_days=400)

        assert len(result) == len(long_end)
        assert result.iloc[-1] > 0  # driven by the weak 30Y, not the strong 2Y

    def test_window_with_too_few_auctions_is_nan(self):
        long_end = _auctions(TRAILING_BTC + [2.3], term="30Y")
        components = {"btc": Component("bid_to_cover", sign=-1, weight=1.0)}
        scored = auction_stress_score(long_end, components=components, min_components=1)

        # Monthly auctions; a 40-day window can hold at most two.
        result = long_end_stress(scored, min_auctions=5, window_days=40)
        assert result.isna().all()

    def test_no_long_end_auctions_returns_empty(self):
        df = _auctions(TRAILING_BTC + [2.3], term="2Y")
        components = {"btc": Component("bid_to_cover", sign=-1, weight=1.0)}
        scored = auction_stress_score(df, components=components, min_components=1)
        assert long_end_stress(scored).empty
