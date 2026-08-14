"""Point-in-time percentile ranks.

This module is the reason the backtest can be believed. A percentile computed over
the full sample ranks a 2005 reading against data running through 2026 — the score
would then "detect" the 2020 bill surge using information from 2024. The result
looks excellent and means nothing.

Every percentile used in a signal is therefore computed **as of each date**, from a
trailing or expanding window containing only data available at that date. The
defining property is tested directly: appending later observations must never
change an earlier percentile.

See docs/implementation_plan.md, Deviation D1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

VALID_METHODS = {"weak", "mid"}


def _rank_within(window: np.ndarray, value: float, method: str) -> float:
    """Percentile of `value` within `window`, both already NaN-free."""
    n = window.size
    if n == 0:
        return np.nan
    below = np.count_nonzero(window < value)
    equal = np.count_nonzero(window == value)
    if method == "weak":
        # Fraction at or below. The running maximum scores 100.
        return 100.0 * (below + equal) / n
    # Midrank: ties share the interval they span. The maximum scores below 100,
    # which is the fairer treatment when a value repeats often.
    return 100.0 * (below + 0.5 * equal) / n


def point_in_time_percentile(
    s: pd.Series,
    *,
    min_periods: int,
    window: int | None = None,
    method: str = "weak",
) -> pd.Series:
    """Percentile rank of each observation against only its own past.

    Parameters
    ----------
    s
        Ordered series. Index may be Period, Datetime or integer; it is used for
        alignment only and is assumed already sorted.
    min_periods
        Minimum number of non-NaN observations in the window (the current
        observation included) before a percentile is published. Below this the
        result is NaN — a percentile from four observations is noise wearing a
        number, and publishing it is worse than publishing nothing.
    window
        Trailing window length in observations. `None` means expanding: rank
        against all history to date.
    method
        'weak' (fraction at or below, default) or 'mid' (ties share their span).

    Returns
    -------
    Series of percentiles in [0, 100], aligned to `s`, NaN where undefined.
    """
    if method not in VALID_METHODS:
        raise ValueError(f"method must be one of {sorted(VALID_METHODS)}, got {method!r}")
    if min_periods < 1:
        raise ValueError("min_periods must be at least 1")
    if window is not None and window < min_periods:
        raise ValueError(
            f"window ({window}) must be at least min_periods ({min_periods})"
        )

    values = pd.to_numeric(s, errors="coerce").to_numpy(dtype="float64")
    n = values.size
    out = np.full(n, np.nan)

    for i in range(n):
        current = values[i]
        if np.isnan(current):
            continue

        start = 0 if window is None else max(0, i - window + 1)
        # Slice ends at i inclusive: only data available as of this observation.
        hist = values[start : i + 1]
        hist = hist[~np.isnan(hist)]

        if hist.size < min_periods:
            continue
        out[i] = _rank_within(hist, current, method)

    return pd.Series(out, index=s.index, name=s.name)


def percentile_of_latest(
    s: pd.Series, *, min_periods: int, window: int | None = None, method: str = "weak"
) -> float:
    """Percentile of the most recent non-NaN observation. Convenience for KPI cards."""
    ranked = point_in_time_percentile(
        s, min_periods=min_periods, window=window, method=method
    )
    valid = ranked.dropna()
    return float(valid.iloc[-1]) if len(valid) else float("nan")


def trailing_zscore(
    s: pd.Series, *, min_periods: int, window: int | None = None
) -> pd.Series:
    """Z-score against trailing history, excluding the current observation.

    Used by the auction stress score, where "how does this auction compare to the
    last twelve" is the question — so the current auction must not contribute to
    the mean and standard deviation it is being judged against.
    """
    if min_periods < 2:
        raise ValueError("min_periods must be at least 2 for a standard deviation")

    numeric = pd.to_numeric(s, errors="coerce")
    prior = numeric.shift(1)

    if window is None:
        roll = prior.expanding(min_periods=min_periods)
    else:
        roll = prior.rolling(window=window, min_periods=min_periods)

    mean = roll.mean()
    std = roll.std(ddof=1)
    # A zero or vanishing standard deviation makes the z-score meaningless, not
    # infinite: every prior observation was identical.
    std = std.where(std > 0)

    return (numeric - mean) / std
