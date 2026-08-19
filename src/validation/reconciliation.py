"""Cross-checks against officially published figures.

Validation failures are errors, not warnings. A dashboard that renders a number
it could not reconcile is worse than one that refuses to render: the chart looks
identical either way, and only one of them is defensible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

TOTAL_CLASS = "TOTAL_MARKETABLE"
# Components summed for the reconciliation. TOTAL_MARKETABLE is excluded because
# it is the thing being checked against, not a part of the sum.
COMPONENT_CLASSES = ("BILLS", "NOTES", "BONDS", "TIPS", "FRN", "OTHER")


@dataclass
class ReconciliationResult:
    """Per-period comparison of summed components against a published total."""

    n_periods: int
    tolerance_pct: float
    breaches: pd.DataFrame = field(default_factory=pd.DataFrame)
    max_abs_diff: float = 0.0
    max_abs_diff_pct: float = 0.0

    @property
    def ok(self) -> bool:
        return self.breaches.empty

    def raise_if_failed(self) -> None:
        if self.ok:
            return
        worst = self.breaches.nlargest(3, "abs_diff_pct")
        raise ValueError(
            f"{len(self.breaches)} period(s) where summed components differ from the "
            f"published {TOTAL_CLASS} by more than {self.tolerance_pct}%. Worst:\n"
            f"{worst.to_string(index=False)}"
        )


def reconcile_components_to_total(
    debt_outstanding: pd.DataFrame,
    *,
    tolerance_pct: float,
    date_col: str = "observation_date",
    class_col: str = "security_class",
    value_col: str = "amount_outstanding",
) -> ReconciliationResult:
    """Check that the component classes sum to the published marketable total.

    The published total is carried as its own row precisely so this check has
    something independent to test against. Treasury rounds published figures, so
    the tolerance is a percentage rather than exact equality — observed residuals
    across 2001-2026 are about $1mn on $27tn, or 4e-6 percent.
    """
    df = debt_outstanding.copy()
    df[class_col] = df[class_col].astype(str)

    wide = df.pivot_table(
        index=date_col, columns=class_col, values=value_col, aggfunc="sum"
    )
    if TOTAL_CLASS not in wide.columns:
        raise ValueError(f"no {TOTAL_CLASS} rows to reconcile against")

    present = [c for c in COMPONENT_CLASSES if c in wide.columns]
    # A class absent in a given month is genuinely absent (FRNs before 2014,
    # Federal Financing Bank in parts of 2002-2004), so skipna is correct here —
    # unlike in net issuance, where a gap after first observation is a real gap.
    summed = wide[present].sum(axis=1, skipna=True)
    total = wide[TOTAL_CLASS]

    diff = summed - total
    diff_pct = (diff / total.where(total != 0)).abs() * 100

    comparison = pd.DataFrame(
        {
            "period": wide.index,
            "sum_of_components": summed.values,
            "published_total": total.values,
            "abs_diff": diff.abs().values,
            "abs_diff_pct": diff_pct.values,
        }
    )
    breaches = comparison[comparison["abs_diff_pct"] > tolerance_pct]

    return ReconciliationResult(
        n_periods=len(comparison),
        tolerance_pct=tolerance_pct,
        breaches=breaches,
        max_abs_diff=float(comparison["abs_diff"].max() or 0.0),
        max_abs_diff_pct=float(comparison["abs_diff_pct"].max() or 0.0),
    )


def reconcile_detail_to_published_subtotal(
    securities: pd.DataFrame,
    subtotals: pd.DataFrame,
    *,
    tolerance_pct: float,
    known_defects: list[dict] | None = None,
) -> ReconciliationResult:
    """Check the security-level detail against Treasury's own per-class subtotal.

    This is the check that makes WAM publishable. WAM is computed from the
    security rows, so if those rows do not reproduce the published unmatured total
    for their class, the weights are wrong and the resulting average is wrong in a
    way nothing downstream would reveal.

    The comparison is against the UNMATURED subtotal, not the class total. Matured
    but unredeemed securities remain outstanding debt and are inside the class
    total — for FRNs in 2023-04 that was $85bn on $601bn — but they carry no
    remaining maturity and so are correctly outside a duration calculation. A
    check against the class total would fail for a legitimate reason and hide any
    real break behind it.
    """
    detail = (
        securities.groupby(["observation_date", "security_class"], observed=True)[
            "amount_outstanding"
        ]
        .sum()
        .rename("detail")
    )
    published = (
        subtotals[subtotals["kind"] == "unmatured"]
        .groupby(["observation_date", "security_class"], observed=True)["amount"]
        .sum()
        .rename("published")
    )

    joined = pd.concat([detail, published], axis=1).dropna()
    diff = (joined["detail"] - joined["published"]).abs()
    diff_pct = (diff / joined["published"].abs().where(joined["published"] != 0)) * 100

    comparison = joined.reset_index()
    comparison["abs_diff"] = diff.values
    comparison["abs_diff_pct"] = diff_pct.values
    comparison = comparison.rename(
        columns={"detail": "sum_of_components", "published": "published_total"}
    )
    breaches = comparison[comparison["abs_diff_pct"] > tolerance_pct]

    # Documented defects in Treasury's own published subtotals are excluded by
    # exact (date, class), never by loosening the tolerance — which would blind
    # the check everywhere else at the same time.
    for defect in known_defects or []:
        breaches = breaches[
            ~(
                (breaches["observation_date"] == pd.Timestamp(defect["observation_date"]))
                & (breaches["security_class"].astype(str) == defect["security_class"])
            )
        ]

    return ReconciliationResult(
        n_periods=len(comparison),
        tolerance_pct=tolerance_pct,
        breaches=breaches,
        max_abs_diff=float(comparison["abs_diff"].max() or 0.0),
        max_abs_diff_pct=float(comparison["abs_diff_pct"].max() or 0.0),
    )
