"""Period-grid helpers.

Every change-over-time calculation in this project runs through here for one
reason: `Series.diff(3)` means "three rows back", not "three months back". If a
month is missing from the data, a naive diff silently compares across the gap and
reports a 4-month change as a 3-month change. That is exactly the class of error
that produces a confident wrong number on a dashboard.

The rule: reindex to a complete period grid first, so a missing observation stays
missing and every difference that touches it becomes NaN.
"""

from __future__ import annotations

import pandas as pd

VALID_FREQ = {"M", "Q"}


def ensure_complete(s: pd.Series, freq: str | None = None) -> pd.Series:
    """Reindex a PeriodIndex Series onto a gap-free period grid.

    Missing periods are inserted as NaN rather than closed up. Returns a sorted
    copy; the input is not modified.
    """
    if not isinstance(s.index, pd.PeriodIndex):
        raise TypeError(f"expected a PeriodIndex, got {type(s.index).__name__}")
    if s.index.has_duplicates:
        dupes = s.index[s.index.duplicated()].unique().tolist()
        raise ValueError(f"duplicate periods in index: {dupes[:5]}")

    freq = freq or s.index.freqstr
    s = s.sort_index()
    if len(s) == 0:
        return s

    full = pd.period_range(s.index.min(), s.index.max(), freq=freq)
    return s.reindex(full)


def period_change(s: pd.Series, periods: int, *, freq: str | None = None) -> pd.Series:
    """Absolute change over `periods` periods, on a gap-free grid."""
    if periods <= 0:
        raise ValueError("periods must be positive")
    complete = ensure_complete(s, freq)
    return complete - complete.shift(periods)


def period_pct_change(s: pd.Series, periods: int, *, freq: str | None = None) -> pd.Series:
    """Fractional change over `periods` periods, on a gap-free grid.

    Computed explicitly rather than via `pct_change`, whose fill behaviour has
    varied across pandas versions — an implicit forward-fill here would invent
    data across exactly the gaps `ensure_complete` exists to preserve.
    """
    if periods <= 0:
        raise ValueError("periods must be positive")
    complete = ensure_complete(s, freq)
    prior = complete.shift(periods)
    # A zero prior value makes the ratio meaningless rather than infinite.
    prior = prior.where(prior != 0)
    return complete / prior - 1.0


def to_period_index(df: pd.DataFrame, date_col: str, freq: str) -> pd.DataFrame:
    """Convert a date column to a PeriodIndex of the given frequency."""
    if freq not in VALID_FREQ:
        raise ValueError(f"freq must be one of {sorted(VALID_FREQ)}, got {freq!r}")
    out = df.copy()
    out.index = pd.PeriodIndex(pd.to_datetime(out[date_col]), freq=freq)
    return out.drop(columns=[date_col])
