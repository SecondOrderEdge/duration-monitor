"""Curve spreads — context only, and honest about holes."""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.calculations.curves import CurveError, spread_context, spread_series

DEFS = {"2s10s": {"long": "DGS10", "short": "DGS2"}}


def _rates(n=30, gap_in_dgs10=None):
    dates = pd.bdate_range("2024-01-01", periods=n)
    rows = []
    for i, d in enumerate(dates):
        rows.append({"date": d, "series_id": "DGS2", "value": 4.0})
        v10 = np.nan if (gap_in_dgs10 and i in gap_in_dgs10) else 4.5 + i * 0.01
        rows.append({"date": d, "series_id": "DGS10", "value": v10})
    return pd.DataFrame(rows)


def test_spread_is_long_minus_short():
    s = spread_series(_rates(), DEFS)
    assert s["2s10s"].iloc[0] == pytest.approx(0.5)


def test_a_hole_in_either_leg_stays_a_hole():
    """DGS20 has a verified 2,466-day gap; a filled spread would manufacture
    readings across it."""
    s = spread_series(_rates(gap_in_dgs10={3, 4}), DEFS)
    assert s["2s10s"].isna().sum() == 2


def test_a_missing_series_raises_rather_than_dropping_the_spread():
    with pytest.raises(CurveError):
        spread_series(_rates(), {"5s30s": {"long": "DGS30", "short": "DGS5"}})


def test_percentile_matches_the_weak_convention():
    """Fraction at or below — same convention as the score's ranks, so the two
    numbers never mean subtly different things on one page."""
    s = spread_series(_rates(), DEFS)   # strictly rising spread
    ctx = spread_context(s, window_years=10)
    assert ctx["percentile"].iloc[0] == pytest.approx(100.0)


def test_context_survives_a_series_shorter_than_the_window():
    ctx = spread_context(spread_series(_rates(), DEFS), window_years=10)
    assert ctx["window_observations"].iloc[0] == 30
    assert np.isnan(ctx["change_12m"].iloc[0])


def test_shipped_config_names_only_ingested_series():
    """The configured legs must exist in the FRED series list, or the page dies
    at render time instead of config-review time."""
    import yaml

    root = pathlib.Path(__file__).resolve().parents[1]
    curves = yaml.safe_load((root / "config" / "thresholds.yaml").read_text())["curves"]
    fred = yaml.safe_load((root / "config" / "sources.yaml").read_text())["fred"]
    # `series` is grouped by purpose (rates, liquidity, ...); flatten the groups.
    ingested = {sid for group in fred["series"].values() for sid in group}
    for name, legs in curves["spreads"].items():
        for role in ("long", "short"):
            assert legs[role] in ingested, f"{name} needs {legs[role]}, not ingested"
