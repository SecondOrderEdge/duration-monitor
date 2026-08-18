"""Bill share, net issuance and the bill-funding ratios.

Two hazards drive the design here.

**Denominators.** Total net marketable borrowing passes through zero — most
notably during binding debt-ceiling episodes, when Treasury runs bills down and
net borrowing collapses toward nothing. A ratio computed there is not merely
noisy, it is unbounded and will dominate any chart it appears on. Ratios are
therefore masked when the denominator is small in absolute terms, and the mask is
reported rather than hidden (Deviations D5).

**TIPS.** Month-over-month change in TIPS outstanding includes inflation
accretion, so it is not net issuance. Left uncorrected it inflates the coupon
aggregate during high-inflation periods and understates incremental bill funding —
a bias that runs *against* the thesis being tested. `coupon_classes` therefore
defaults to excluding TIPS, and the choice is recorded on the output
(Deviation D2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .timegrid import ensure_complete, period_change

BILL_CLASS = "BILLS"
TOTAL_CLASS = "TOTAL_MARKETABLE"
DEFAULT_COUPON_CLASSES = ("NOTES", "BONDS", "FRN")

# Rows MSPD publishes that are aggregates of other rows. Summing over them would
# double-count, so they are only ever used directly, never in a sum.
AGGREGATE_CLASSES = frozenset({TOTAL_CLASS})


def _pivot_strict(
    df: pd.DataFrame, *, index: str, columns: str, values: str
) -> pd.DataFrame:
    """Pivot to wide form without inventing or absorbing anything.

    `pivot_table(aggfunc="sum")` is unusable here for two reasons: it turns a
    missing observation into 0.0, which is a silent fill of exactly the kind this
    project forbids, and it quietly sums duplicate keys — so passing multi-country
    data to a per-country calculation would add the countries together and return
    a plausible wrong number.

    This raises on duplicate keys and preserves NaN.
    """
    duplicated = df.duplicated(subset=[index, columns])
    if duplicated.any():
        examples = (
            df.loc[duplicated, [index, columns]]
            .drop_duplicates()
            .head(3)
            .to_dict("records")
        )
        raise ValueError(
            f"duplicate ({index}, {columns}) keys, e.g. {examples}; these functions "
            "expect one row per period per security class — filter to a single "
            "country before calling"
        )
    return df.pivot(index=index, columns=columns, values=values)


def bill_share(
    debt_outstanding: pd.DataFrame,
    *,
    date_col: str = "observation_date",
    class_col: str = "security_class",
    value_col: str = "amount_outstanding",
) -> pd.Series:
    """Bills as a fraction of total marketable debt, indexed by period.

    The denominator is the *published* TOTAL_MARKETABLE row, never a sum of the
    component classes. That is deliberate: it keeps the reconciliation check in
    the validation layer meaningful, since a mismatch between the published total
    and the sum of parts is a real data problem worth surfacing rather than
    something to define away.
    """
    df = debt_outstanding.copy()
    df[date_col] = pd.PeriodIndex(pd.to_datetime(df[date_col]), freq="M")

    wide = _pivot_strict(df, index=date_col, columns=class_col, values=value_col)

    for required in (BILL_CLASS, TOTAL_CLASS):
        if required not in wide.columns:
            raise ValueError(
                f"debt_outstanding has no {required!r} rows; bill share needs both "
                f"{BILL_CLASS!r} and the published {TOTAL_CLASS!r} total"
            )

    total = wide[TOTAL_CLASS].where(wide[TOTAL_CLASS] > 0)
    share = wide[BILL_CLASS] / total
    share.name = "bill_share"
    return ensure_complete(share)


def bill_share_changes(
    share: pd.Series, *, horizons: tuple[int, ...] = (3, 6, 12)
) -> pd.DataFrame:
    """Absolute changes in bill share over the given month horizons."""
    out = pd.DataFrame({"bill_share": ensure_complete(share)})
    for h in horizons:
        out[f"change_{h}m"] = period_change(share, h)
    return out


def net_issuance(
    debt_outstanding: pd.DataFrame,
    *,
    date_col: str = "observation_date",
    class_col: str = "security_class",
    value_col: str = "amount_outstanding",
    freq: str = "M",
) -> pd.DataFrame:
    """Net issuance by security class, as the period-over-period change in outstanding.

    This is an approximation: MSPD deltas net issuance against redemptions and
    reopenings within the period, and for TIPS they also absorb inflation
    accretion. Documented in docs/methodology.md; the `method` column records it
    on every row.

    A class with a missing prior period yields NaN, never a change measured across
    the gap.
    """
    df = debt_outstanding.copy()
    df[date_col] = pd.PeriodIndex(pd.to_datetime(df[date_col]), freq=freq)

    wide = _pivot_strict(
        df, index=date_col, columns=class_col, values=value_col
    ).sort_index()

    if len(wide):
        full = pd.period_range(wide.index.min(), wide.index.max(), freq=freq)
        wide = wide.reindex(full)

    deltas = wide - wide.shift(1)

    out = (
        deltas.stack(future_stack=True)
        .rename("net_issuance")
        .reset_index()
        .rename(columns={"level_0": "period", class_col: "security_class"})
    )
    out.columns = ["period", "security_class", "net_issuance"]
    out["method"] = "mspd_delta"
    return out


def _aggregate(net: pd.DataFrame, classes) -> pd.Series:
    """Sum net issuance across the given classes, per period.

    A security class is treated as **structurally absent** until its first
    observation and **active** from that point on. This distinction matters:
    FRNs did not exist before 2014 and TIPS before 1997, so requiring every
    configured class to be present in every period would void two decades of
    history. Conversely, a class that has started reporting and then goes missing
    is a real data gap, and a partial sum there would understate the aggregate
    while looking complete.

    So: absent-and-never-seen is excluded; missing-after-first-observation
    propagates NaN. A period in which no configured class is yet active is NaN,
    since there is nothing to aggregate.
    """
    classes = list(classes)
    subset = net[net["security_class"].isin(classes)]

    wide = _pivot_strict(
        subset, index="period", columns="security_class", values="net_issuance"
    )

    # Cover every period in the input, including those with no rows for these classes.
    all_periods = pd.Index(sorted(net["period"].unique()), name="period")
    wide = wide.reindex(all_periods)

    for c in classes:
        if c not in wide.columns:
            wide[c] = np.nan
    wide = wide[classes]

    active = wide.notna().cummax()          # True from each class's first observation
    genuine_gap = active & wide.isna()      # active but missing => real gap

    total = wide.sum(axis=1, skipna=True)
    total = total.where(~genuine_gap.any(axis=1))   # any real gap voids the period
    total = total.where(active.any(axis=1))         # nothing active yet => nothing to sum
    return total


def incremental_bill_funding(
    net: pd.DataFrame,
    *,
    coupon_classes: tuple[str, ...] = DEFAULT_COUPON_CLASSES,
    min_abs_denominator: float,
) -> pd.DataFrame:
    """Share of net marketable borrowing absorbed by bills.

    The denominator is net bills plus net coupons, built from the component
    classes so that it matches the numerator's basis exactly — using the published
    total instead would mix an accretion-contaminated TIPS figure into the
    denominator while the numerator excludes it.

    Periods where |denominator| < `min_abs_denominator` are masked to NaN and
    flagged. There is no meaningful "share of borrowing" when there is no net
    borrowing to share.
    """
    if min_abs_denominator <= 0:
        raise ValueError("min_abs_denominator must be positive")

    bills = _aggregate(net, [BILL_CLASS])
    coupons = _aggregate(net, coupon_classes)
    denominator = bills + coupons

    # One flag with one meaning: the ratio is not published because the
    # denominator is either unavailable or too small to divide by.
    masked = denominator.isna() | (denominator.abs() < min_abs_denominator)
    safe = denominator.where(~masked)

    out = pd.DataFrame(
        {
            "net_bills": bills,
            "net_coupons": coupons,
            "net_total": denominator,
            "incremental_bill_funding": bills / safe,
            "denominator_masked": masked,
        }
    )
    out["coupon_classes"] = ",".join(coupon_classes)
    out.index.name = "period"
    return out


def bill_to_coupon_ratio(
    net: pd.DataFrame,
    *,
    coupon_classes: tuple[str, ...] = DEFAULT_COUPON_CLASSES,
    min_abs_denominator: float,
) -> pd.DataFrame:
    """Ratio of net bill to net coupon issuance, with the same denominator guard.

    Note the ratio is signed and unbounded by nature: negative net coupon issuance
    with positive net bills is a genuine and highly relevant configuration, so the
    sign is preserved rather than clipped. Read it alongside
    `incremental_bill_funding`, which is bounded and easier to interpret.
    """
    if min_abs_denominator <= 0:
        raise ValueError("min_abs_denominator must be positive")

    bills = _aggregate(net, [BILL_CLASS])
    coupons = _aggregate(net, coupon_classes)

    masked = coupons.isna() | (coupons.abs() < min_abs_denominator)
    safe = coupons.where(~masked)

    out = pd.DataFrame(
        {
            "net_bills": bills,
            "net_coupons": coupons,
            "bill_to_coupon_ratio": bills / safe,
            "denominator_masked": masked,
        }
    )
    out.index.name = "period"
    return out


def aggregate_net_issuance(
    net: pd.DataFrame, *, freq: str = "Q", period_col: str = "period"
) -> pd.DataFrame:
    """Roll monthly net issuance up to a coarser period.

    Net issuance is a FLOW, so aggregating it means summing the monthly changes
    within each period — not recomputing the change on a coarser calendar. Passing
    monthly data to `net_issuance(freq="Q")` instead maps three months onto one
    period key and raises, which is the guard working: the two operations give
    different answers and only one of them is net issuance.

    A period containing any missing month is voided rather than partially summed.
    A quarter reported as two months of issuance looks like a real, smaller number
    and there is nothing in the output to say otherwise.
    """
    df = net.copy()
    df[period_col] = df[period_col].dt.asfreq(freq)

    grouped = df.groupby([period_col, "security_class"], observed=True)["net_issuance"]
    summed = grouped.sum(min_count=1)

    # Two distinct ways a period can be incomplete, and only one of them leaves a
    # NaN behind to find:
    #   a month is present but unmeasurable (no prior observation to difference), or
    #   a month is absent from the input entirely — which is the normal state of
    #   the trailing period, since the source publishes monthly and the current
    #   quarter is partial until its third month lands.
    # The second is the dangerous one: one month of issuance summed and labelled
    # as a quarter is a complete-looking bar a third the height it will end up.
    has_nan = grouped.apply(lambda s: s.isna().any())
    months_present = grouped.apply(lambda s: len(s))
    months_expected = pd.Series(
        [
            len(pd.period_range(p.start_time, p.end_time, freq="M"))
            for p, _ in months_present.index
        ],
        index=months_present.index,
    )
    incomplete = has_nan | (months_present < months_expected)

    out = summed.where(~incomplete).rename("net_issuance").reset_index()
    out["method"] = "mspd_delta"
    out["period_complete"] = (~incomplete).values
    return out
