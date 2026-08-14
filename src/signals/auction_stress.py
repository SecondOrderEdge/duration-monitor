"""Auction stress score.

Measures how well each auction was absorbed relative to the recent history of the
*same tenor*, since a 30-year auction and a 2-year auction are not comparable on
any of these metrics.

**Sign convention: higher means weaker.** A positive score is a poorly absorbed
auction.

- bid-to-cover below its trailing average  → weak (sign -1)
- indirect participation below average     → weak (sign -1)
- primary dealer takedown above average    → weak (sign +1), dealers are the
  residual buyer and absorb what others decline
- tail above average                       → weak (sign +1)

**On the tail component (Deviation D3).** A true tail needs the 1pm when-issued
yield, which is not free. The fallback proxy — high yield against a constant
maturity par yield at the close — absorbs a full day of market movement plus a
maturity-point mismatch, and is mostly noise about something other than auction
quality. It therefore carries **zero default weight** and is computed as a
diagnostic only. If the source probe confirms Treasury publishes low/median yield
and allotment-at-high, the high-minus-median spread is a genuine official measure
of bid dispersion and should replace it at a real weight.

Weights are injected by the caller from `config/factor_weights.yaml`; nothing in
this module reads configuration.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.calculations.percentiles import trailing_zscore


@dataclass(frozen=True)
class Component:
    """One input to the composite: which column, which direction, how much weight."""

    column: str
    sign: int  # +1 if a high value means a weak auction, -1 if a low value does
    weight: float

    def __post_init__(self) -> None:
        if self.sign not in (-1, 1):
            raise ValueError(f"sign must be +1 or -1, got {self.sign}")
        if self.weight < 0:
            raise ValueError(f"weight must be non-negative, got {self.weight}")


# Defaults reflect Deviation D3: the three genuine absorption measures carry the
# score; the CMT-based tail proxy is carried at zero weight until a real
# dispersion measure is confirmed available.
DEFAULT_COMPONENTS: dict[str, Component] = {
    "bid_to_cover": Component("bid_to_cover", sign=-1, weight=1.0),
    "indirect": Component("indirect_pct", sign=-1, weight=1.0),
    "dealer": Component("primary_dealer_pct", sign=+1, weight=1.0),
    "tail": Component("tail_proxy_bps", sign=+1, weight=0.0),
}

LONG_END_TERMS = ("10Y", "20Y", "30Y")

DEFAULT_TRAILING_AUCTIONS = 12
DEFAULT_SCALE_SIGMA = 3.0


def component_zscores(
    auctions: pd.DataFrame,
    *,
    components: dict[str, Component] | None = None,
    tenor_col: str = "term",
    date_col: str = "auction_date",
    trailing_auctions: int = DEFAULT_TRAILING_AUCTIONS,
    min_trailing: int | None = None,
) -> pd.DataFrame:
    """Trailing z-score of each component, computed within each tenor.

    The trailing window excludes the auction being scored, so an auction is judged
    against the ones before it and never against itself.

    Auctions with fewer than `min_trailing` prior observations of the same tenor
    score NaN rather than a partial-window value.
    """
    components = components or DEFAULT_COMPONENTS
    min_trailing = min_trailing or trailing_auctions

    if min_trailing < 2:
        raise ValueError("min_trailing must be at least 2 to form a standard deviation")
    for required in (tenor_col, date_col):
        if required not in auctions.columns:
            raise ValueError(f"auctions is missing required column {required!r}")

    df = auctions.sort_values([tenor_col, date_col]).copy()

    for name, spec in components.items():
        col = f"z_{name}"
        if spec.column not in df.columns:
            # A component the feed does not carry is absent, not zero.
            df[col] = np.nan
            continue
        df[col] = (
            df.groupby(tenor_col, dropna=False, observed=True)[spec.column]
            .transform(
                lambda s: trailing_zscore(
                    s, min_periods=min_trailing, window=trailing_auctions
                )
            )
        )

    return df


def auction_stress_score(
    auctions: pd.DataFrame,
    *,
    components: dict[str, Component] | None = None,
    tenor_col: str = "term",
    date_col: str = "auction_date",
    trailing_auctions: int = DEFAULT_TRAILING_AUCTIONS,
    min_trailing: int | None = None,
    min_components: int = 2,
    scale_sigma: float = DEFAULT_SCALE_SIGMA,
) -> pd.DataFrame:
    """Per-auction stress score, roughly -100 (exceptionally strong) to +100 (weak).

    The composite is a weighted mean of signed component z-scores, renormalised
    over whichever components are actually available for that auction. An auction
    with fewer than `min_components` available scores NaN — a "composite" resting
    on one input is not a composite.

    Scaling maps ±`scale_sigma` standard deviations onto ±100 and clips beyond it.
    The clip is deliberate: it bounds the axis so one extraordinary auction cannot
    flatten the rest of the history, and it is recorded in `score_clipped` so the
    loss of resolution is visible rather than silent.
    """
    if scale_sigma <= 0:
        raise ValueError("scale_sigma must be positive")
    if min_components < 1:
        raise ValueError("min_components must be at least 1")

    components = components or DEFAULT_COMPONENTS
    active = {name: spec for name, spec in components.items() if spec.weight > 0}
    if not active:
        raise ValueError("no component carries a non-zero weight")

    df = component_zscores(
        auctions,
        components=components,
        tenor_col=tenor_col,
        date_col=date_col,
        trailing_auctions=trailing_auctions,
        min_trailing=min_trailing,
    )

    weighted_sum = pd.Series(0.0, index=df.index)
    weight_total = pd.Series(0.0, index=df.index)
    available = pd.Series(0, index=df.index)

    for name, spec in active.items():
        z = df[f"z_{name}"]
        present = z.notna()
        weighted_sum = weighted_sum.add((spec.sign * z * spec.weight).fillna(0.0))
        weight_total = weight_total.add(present * spec.weight)
        available = available.add(present.astype(int))

    composite = weighted_sum / weight_total.where(weight_total > 0)
    composite = composite.where(available >= min_components)

    scaled = (composite / scale_sigma) * 100.0
    df["stress_z"] = composite
    df["stress_score"] = scaled.clip(-100.0, 100.0)
    df["score_clipped"] = scaled.notna() & (scaled.abs() > 100.0)
    df["n_components"] = available
    df["components_used"] = ",".join(sorted(active))

    return df


def long_end_stress(
    scored: pd.DataFrame,
    *,
    date_col: str = "auction_date",
    tenor_col: str = "term",
    terms: tuple[str, ...] = LONG_END_TERMS,
    window_days: int = 90,
    min_auctions: int = 3,
) -> pd.Series:
    """Rolling mean stress across long-end auctions.

    Averaged over a *time* window rather than a fixed auction count, so the series
    reflects a consistent period regardless of how many auctions the calendar
    happened to place in it. Windows containing fewer than `min_auctions` return
    NaN.
    """
    subset = scored[scored[tenor_col].isin(list(terms))].copy()
    if subset.empty:
        return pd.Series(dtype="float64", name="long_end_stress")

    subset[date_col] = pd.to_datetime(subset[date_col])
    subset = subset.sort_values(date_col).set_index(date_col)

    roll = subset["stress_score"].rolling(f"{window_days}D", min_periods=min_auctions)
    out = roll.mean()
    out.name = "long_end_stress"
    return out
