"""Fiscal Duration Shift Score.

A 0-100 composite of six factors, each converted to a point-in-time percentile
rank so that a reading at date *t* is ranked only against data available at *t*
(Deviation D1). Higher means a more aggressive shortening of the financing
profile.

**On the weights.** The six factors are not six pieces of information. Measured
on the percentile ranks the score actually uses, bill share trend, WAM trend and
coupon restraint are mutually correlated 0.91-0.97 — and at matched horizons,
incremental bill funding and coupon restraint are the same number, because bill
share of financing is one minus coupon share of financing. Equal weights would
therefore give one measurement roughly half the score while the only orthogonal
factor, auction stress, received a sixth.

The weights are instead derived from the correlation structure, `w ∝ C⁻¹1`, so
redundancy is penalised by the data rather than by judgement. Every factor is
retained: the brief's six stay six, and a factor that duplicates another simply
earns less.

Two properties of that estimator have to be managed rather than assumed away.
The matrix is singular when two factors are perfectly correlated, and the
inversion amplifies small changes in correlation into large changes in weight —
walk-forward, an unshrunk estimate drove one factor to exactly zero in three of
five vintages, silently removing it. Shrinkage toward the identity fixes both,
and the amount is chosen by walk-forward stability: at 0.5 no factor is ever
zeroed and the largest drift across vintages halves.

Weights are computed on an expanding window for the same reason the percentiles
are point-in-time. Fitting them on the full sample would leak the future into a
backtest through the weighting, which is exactly the contamination D1 exists to
prevent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.calculations.percentiles import point_in_time_percentile

# Direction is fixed in code — higher always means more shortening — so config
# carries only weights, and no configuration change can silently invert a factor.
FACTOR_DIRECTION = {
    "bill_share_trend": +1,
    "incremental_bill_funding": +1,
    # Falling WAM means shortening.
    "wam_trend": -1,
    # `build_factors` computes the COUPON SHARE of financing need, so a high
    # value means coupons kept pace — the opposite of restraint. Getting this
    # sign wrong does not break anything visibly: the score stays in range, the
    # chart still looks like a plausible series, and the only symptom is that
    # the 2020 spike the brief says MUST appear flattens to +3 points.
    "coupon_restraint": -1,
    "term_premium_10y_trend": +1,
    "long_end_auction_stress": +1,
}

DEFAULT_RIDGE = 0.5
DEFAULT_MIN_FACTORS = 4
MIN_MONTHS_FOR_WEIGHTS = 36


def percentile_ranks(
    factors: pd.DataFrame, *, window: int, min_periods: int
) -> pd.DataFrame:
    """Point-in-time percentile rank of each factor against its own past.

    Ranking is what makes the score robust to outliers: an extreme observation
    becomes the 100th percentile and can go no further, so a crisis cannot drag
    the scale the way it would in a z-score composite. Removing 2008-09 and
    2020-21 from estimation moves the finished score by under one point.
    """
    return pd.DataFrame(
        {
            name: point_in_time_percentile(
                series.dropna(), min_periods=min_periods, window=window
            )
            for name, series in factors.items()
        }
    ).sort_index()


def correlation_weights(
    ranks: pd.DataFrame, *, ridge: float = DEFAULT_RIDGE
) -> pd.Series:
    """Weights proportional to C⁻¹1, shrunk toward equal weighting.

    `ridge` is the shrinkage toward the identity matrix. It is not cosmetic: at
    0 the matrix is singular whenever two factors are perfectly correlated, and
    at small values the weights are unstable walk-forward and can be clipped to
    zero, which removes a factor the model is supposed to retain.
    """
    if not 0 < ridge < 1:
        raise ValueError(f"ridge must be in (0, 1), got {ridge}")

    names = list(ranks.columns)
    if len(names) < 2:
        return pd.Series(1.0, index=names)

    corr = ranks.corr(method="spearman").to_numpy(dtype=float)
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)

    shrunk = (1.0 - ridge) * corr + ridge * np.eye(len(names))
    raw = np.linalg.solve(shrunk, np.ones(len(names)))

    # A negative weight would mean "a worse reading on this factor improves the
    # score", which is not a thing this composite can express. Clipped, then
    # renormalised — with adequate shrinkage this branch does not trigger.
    raw = np.clip(raw, 0.0, None)
    if raw.sum() <= 0:
        return pd.Series(1.0 / len(names), index=names)
    return pd.Series(raw / raw.sum(), index=names)


def expanding_weights(
    ranks: pd.DataFrame,
    *,
    ridge: float = DEFAULT_RIDGE,
    min_months: int = MIN_MONTHS_FOR_WEIGHTS,
) -> pd.DataFrame:
    """Weights as they would have been known at each date.

    Before `min_months` of overlapping history the correlation structure is not
    estimable and the weights fall back to equal — stated, rather than fitted on
    data that did not exist yet.
    """
    names = list(ranks.columns)
    rows: dict = {}
    for i, period in enumerate(ranks.index):
        history = ranks.iloc[: i + 1]
        usable = history.dropna(how="any")
        if len(usable) < min_months:
            rows[period] = pd.Series(1.0 / len(names), index=names)
        else:
            rows[period] = correlation_weights(usable, ridge=ridge)
    return pd.DataFrame(rows).T


def duration_shift_score(
    ranks: pd.DataFrame,
    weights: pd.DataFrame | pd.Series,
    *,
    min_factors: int = DEFAULT_MIN_FACTORS,
) -> pd.DataFrame:
    """Combine ranked factors into the 0-100 score.

    Weights are renormalised over whichever factors are available in each month,
    so a factor that has not started yet does not drag the score toward zero. A
    month with fewer than `min_factors` available scores NaN: a composite resting
    on two inputs is not the same measurement as one resting on six, and
    publishing both under one name would make the series discontinuous in a way
    no chart would reveal.
    """
    names = list(ranks.columns)
    if isinstance(weights, pd.Series):
        weights = pd.DataFrame(
            np.tile(weights[names].to_numpy(), (len(ranks), 1)),
            index=ranks.index, columns=names,
        )
    weights = weights.reindex(ranks.index)[names]

    available = ranks.notna()
    weighted = (ranks.fillna(0.0) * weights).sum(axis=1)
    total = (available * weights).sum(axis=1)

    score = weighted / total.where(total > 0)
    n_available = available.sum(axis=1)

    out = pd.DataFrame(
        {
            "score": score.where(n_available >= min_factors),
            "n_factors": n_available,
        }
    )
    # Contribution of each factor, so a reading can always be explained.
    for name in names:
        out[f"contrib_{name}"] = (
            ranks[name].fillna(0.0) * weights[name] / total.where(total > 0)
        ).where(n_available >= min_factors)
    return out


def score_band(score: pd.Series, bands: list[dict]) -> pd.Series:
    """Map the score onto the named interpretation bands from config.

    Bands are `{name, from, to}` and are treated as [from, to) so a reading of
    exactly 60 lands in "meaningful shortening" rather than "neutral". Boundary
    readings are common — a percentile composite clusters near round numbers —
    so which side they fall on is a stated convention, not an accident.
    """
    ordered = sorted(bands, key=lambda b: b["from"])

    def label(value):
        if pd.isna(value):
            return None
        for band in ordered:
            if value < band["to"] or band is ordered[-1]:
                if value >= band["from"]:
                    return band["name"]
        return ordered[-1]["name"]

    return score.map(label).rename("band")


_COMPARATORS = {
    "_at_least": lambda series, threshold: series >= threshold,
    "_below": lambda series, threshold: series < threshold,
    "_above": lambda series, threshold: series > threshold,
}


def _score_level(score: pd.Series, levels: dict) -> pd.Series:
    """Ordinal regime level implied by the score alone.

    The thresholds start at zero and are ascending, so this is total over the
    score's range: every scored month gets a level.
    """
    edges = [spec["score_at_least"] for spec in levels.values()]
    if edges != sorted(edges) or edges[0] != 0:
        raise ValueError(
            f"regime score thresholds must ascend from 0, got {edges}; otherwise "
            "the levels do not cover the score range"
        )
    return pd.Series(
        np.searchsorted(edges, score.to_numpy(dtype=float), side="right") - 1,
        index=score.index,
    ).where(score.notna())


def classify_regime(inputs: pd.DataFrame, regimes: dict) -> pd.Series:
    """Regime from the score band, capped by how far market evidence corroborates it.

    Two properties this is built to have, both of which the previous scheme
    lacked.

    **Total.** Every scored month gets a regime. Conditions that must ALL hold to
    earn a label leave anything failing them unlabelled — 41% of months, under
    the previous conditions, sat in no regime at all rather than in a low one.
    Here the score band is the base and it partitions the range by construction.

    **Escalation requires corroboration; the absence of it caps rather than
    erases.** Quantity evidence alone is enough to call shortening. Calling
    duration PRESSURE requires the market to agree, so a high score with a
    falling term premium is capped at yellow instead of promoted to orange. That
    is the 2020-versus-2023 distinction: both were bill-heavy, but in 2020 the
    Fed was absorbing the issuance and the term premium fell.

    Corroboration thresholds are percentiles of each input's own point-in-time
    history. Raw levels cannot be calibrated and can be silently unreachable —
    the previous red regime required an auction-stress reading of 25 against a
    series whose observed maximum is 22.4.
    """
    levels = list(regimes["levels"])
    corroboration = regimes.get("corroboration", {})

    band = _score_level(inputs["duration_shift_score"], regimes["levels"])

    # Ceiling starts at the first escalated level: lacking market evidence caps a
    # reading, it never pushes it below what the score alone already established.
    ceiling = pd.Series(1, index=inputs.index, dtype="float64")
    for index, name in enumerate(levels):
        if name not in corroboration:
            continue
        holds = pd.Series(True, index=inputs.index)
        for key, threshold in corroboration[name].items():
            for suffix, compare in _COMPARATORS.items():
                if key.endswith(suffix):
                    column = key[: -len(suffix)]
                    if column not in inputs.columns:
                        raise ValueError(
                            f"regime {name!r} tests {column!r}, which was not "
                            f"supplied; available: {list(inputs.columns)}"
                        )
                    holds &= compare(inputs[column], threshold).fillna(False)
                    break
            else:
                raise ValueError(
                    f"regime {name!r} has condition {key!r} with no recognised "
                    f"comparator suffix ({sorted(_COMPARATORS)})"
                )
        ceiling = ceiling.where(~holds, index)

    # A score in the lowest band is green whatever the market is doing.
    level = pd.concat([band, ceiling], axis=1).min(axis=1).where(band > 0, band)
    return level.map(
        lambda v: levels[int(v)] if pd.notna(v) else None
    ).rename("regime")


def build_factors(
    *,
    bill_share_series: pd.Series,
    net: pd.DataFrame,
    incremental_funding: pd.Series,
    wam_years: pd.Series,
    term_premium_10y: pd.Series,
    auction_stress: pd.Series,
    coupon_classes: tuple[str, ...],
    min_abs_denominator: float,
    horizon: int = 12,
) -> pd.DataFrame:
    """Assemble the six factors on a common monthly axis.

    Signs are applied here so that HIGHER ALWAYS MEANS MORE SHORTENING, and the
    direction of each is fixed in `FACTOR_DIRECTION` rather than in config —
    a weights file should not be able to silently invert a factor's meaning.
    """
    from src.calculations.issuance import _aggregate

    coupons = _aggregate(net, coupon_classes)
    coupons_12m = coupons.rolling(horizon).sum()
    bills_12m = _aggregate(net, ["BILLS"]).rolling(horizon).sum()
    need_12m = bills_12m + coupons_12m

    factors = pd.DataFrame({
        "bill_share_trend": bill_share_series.diff(horizon),
        "incremental_bill_funding": incremental_funding,
        "wam_trend": wam_years.diff(horizon),
        "coupon_restraint": coupons_12m
        / need_12m.where(need_12m.abs() > min_abs_denominator),
        "term_premium_10y_trend": term_premium_10y.diff(horizon),
        "long_end_auction_stress": auction_stress,
    })
    for name, direction in FACTOR_DIRECTION.items():
        factors[name] = factors[name] * direction
    return factors[list(FACTOR_DIRECTION)]
