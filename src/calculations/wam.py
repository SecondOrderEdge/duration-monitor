"""Weighted average maturity and maturity-bucket composition.

WAM = Σ(amount × years to maturity) / Σ(amount), over marketable securities only,
valued at a stated date.

Conventions are explicit parameters rather than buried defaults, because four of
them change the answer (docs/implementation_plan.md, Deviation D9):

1. Final maturity is used for FRNs and TIPS.
2. TIPS weighting basis (par vs inflation-adjusted) is decided upstream and
   carried on the `amount_basis` column; this module asserts it is consistent.
3. Callable bonds in the pre-2009 history mature at final maturity here; call
   dates are not modelled.
4. Non-marketable debt is excluded upstream and never reaches this function.

The computed total is reconciled against published MSPD totals by the validation
layer. A WAM that cannot reproduce the official total is not fit to publish.
"""

from __future__ import annotations

import pandas as pd

DAYS_PER_YEAR = 365.25

REQUIRED_COLUMNS = ("maturity_date", "amount_outstanding")


def _prepare(securities: pd.DataFrame, valuation_date) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in securities.columns]
    if missing:
        raise ValueError(f"securities is missing required columns: {missing}")

    valuation = pd.Timestamp(valuation_date)
    if pd.isna(valuation):
        raise ValueError("valuation_date is required and must be a valid date")

    df = securities.copy()
    df["maturity_date"] = pd.to_datetime(df["maturity_date"], errors="coerce")
    df["amount_outstanding"] = pd.to_numeric(df["amount_outstanding"], errors="coerce")

    # Silently dropping unparseable rows would change the denominator and quietly
    # shift WAM, so these are errors.
    if df["maturity_date"].isna().any():
        bad = int(df["maturity_date"].isna().sum())
        raise ValueError(f"{bad} row(s) have a missing or unparseable maturity_date")
    if df["amount_outstanding"].isna().any():
        bad = int(df["amount_outstanding"].isna().sum())
        raise ValueError(f"{bad} row(s) have a missing or unparseable amount_outstanding")
    if (df["amount_outstanding"] < 0).any():
        raise ValueError("amount_outstanding contains negative values")

    matured = df["maturity_date"] < valuation
    if matured.any():
        n = int(matured.sum())
        earliest = df.loc[matured, "maturity_date"].min().date()
        raise ValueError(
            f"{n} security/securities mature before the valuation date "
            f"{valuation.date()} (earliest {earliest}); a snapshot should contain "
            "only securities outstanding at that date"
        )

    if "amount_basis" in df.columns:
        bases = set(df["amount_basis"].dropna().unique())
        if len(bases) > 1:
            raise ValueError(
                f"mixed amount_basis values {sorted(bases)}; par and "
                "inflation-adjusted amounts cannot be weighted together"
            )

    df["years_to_maturity"] = (df["maturity_date"] - valuation).dt.days / DAYS_PER_YEAR
    return df


def weighted_average_maturity(securities: pd.DataFrame, valuation_date) -> float:
    """WAM in years. NaN if nothing is outstanding."""
    df = _prepare(securities, valuation_date)

    total = df["amount_outstanding"].sum()
    if total <= 0:
        return float("nan")

    return float((df["amount_outstanding"] * df["years_to_maturity"]).sum() / total)


def maturity_buckets(
    securities: pd.DataFrame,
    valuation_date,
    *,
    bucket_years: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0),
) -> pd.Series:
    """Share of outstanding maturing within each horizon.

    Buckets are cumulative and inclusive: the '2y' entry is everything maturing in
    two years or less, so it contains the '1y' entry. Shares are fractions of the
    total, not percentages.
    """
    df = _prepare(securities, valuation_date)

    total = df["amount_outstanding"].sum()
    if total <= 0:
        return pd.Series(
            {f"within_{y:g}y": float("nan") for y in bucket_years}, dtype="float64"
        )

    shares = {
        f"within_{years:g}y": float(
            df.loc[df["years_to_maturity"] <= years, "amount_outstanding"].sum() / total
        )
        for years in bucket_years
    }
    return pd.Series(shares, dtype="float64")


def wam_series(
    securities: pd.DataFrame,
    *,
    date_col: str = "observation_date",
    group_cols: tuple[str, ...] = (),
) -> pd.DataFrame:
    """WAM per observation date, valuing each snapshot at its own date.

    `group_cols` allows WAM by security class or country alongside the total.
    """
    if date_col not in securities.columns:
        raise ValueError(f"securities is missing the date column {date_col!r}")

    records = []
    keys = [date_col, *group_cols]

    for key, snapshot in securities.groupby(keys, dropna=False, observed=True):
        key = key if isinstance(key, tuple) else (key,)
        valuation = key[0]
        row = dict(zip(keys, key))
        row["wam_years"] = weighted_average_maturity(snapshot, valuation)
        row["amount_outstanding"] = float(
            pd.to_numeric(snapshot["amount_outstanding"], errors="coerce").sum()
        )
        row.update(maturity_buckets(snapshot, valuation).to_dict())
        records.append(row)

    return pd.DataFrame.from_records(records).sort_values(keys).reset_index(drop=True)
