"""Curve spreads with historical percentile context.

Calculation 9 of the brief, and deliberately the least ambitious module in the
project: a spread mixes rate expectations with term premium, so it frames a
term-premium reading rather than feeding the score. Nothing here reaches the
signal layer, and nothing should.

Definitions live in config (`curves.spreads`), not here — which pairs of
constant-maturity series constitute "2s10s" is an assumption like any other.
"""

from __future__ import annotations

import pandas as pd

TRADING_DAYS_PER_YEAR = 252


class CurveError(ValueError):
    """The rates table cannot support the configured spreads."""


def spread_series(rates: pd.DataFrame, definitions: dict) -> pd.DataFrame:
    """Daily spreads (long minus short, percentage points) per configured name.

    Missing observations stay missing: DGS20 carries a verified 2,466-day hole,
    and a spread built on a filled series would manufacture readings across it.
    A date where either leg is absent is NaN for that spread.
    """
    required = {"date", "series_id", "value"}
    missing = sorted(required - set(rates.columns))
    if missing:
        raise CurveError(f"rates table is missing {missing}")

    wide = rates.pivot_table(index="date", columns="series_id", values="value",
                             aggfunc="first").sort_index()
    out = {}
    for name, legs in definitions.items():
        for role in ("long", "short"):
            if legs[role] not in wide.columns:
                raise CurveError(
                    f"spread {name!r} needs series {legs[role]!r}, which the "
                    f"rates table does not carry"
                )
        out[name] = wide[legs["long"]] - wide[legs["short"]]
    return pd.DataFrame(out)


def spread_context(spreads: pd.DataFrame, *, window_years: int) -> pd.DataFrame:
    """Latest level, changes and trailing percentile per spread.

    The percentile is of the latest reading against its own trailing window —
    weak ranking (fraction at or below), matching the score's percentile
    convention so the two numbers never mean subtly different things on one page.
    """
    if window_years <= 0:
        raise CurveError("window_years must be positive")
    window = window_years * TRADING_DAYS_PER_YEAR

    rows = []
    for name in spreads.columns:
        s = spreads[name].dropna()
        if s.empty:
            rows.append({"spread": name, "latest": float("nan")})
            continue
        tail = s.iloc[-window:]
        latest = s.iloc[-1]
        rows.append({
            "spread": name,
            "latest": float(latest),
            "change_3m": float(latest - s.iloc[-64]) if len(s) > 64 else float("nan"),
            "change_12m": float(latest - s.iloc[-TRADING_DAYS_PER_YEAR])
                          if len(s) > TRADING_DAYS_PER_YEAR else float("nan"),
            "percentile": float((tail <= latest).mean() * 100),
            "window_observations": int(len(tail)),
            "as_of": s.index[-1],
        })
    return pd.DataFrame(rows)
