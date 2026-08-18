"""Raw fiscaldata responses to the normalized `debt_outstanding` table.

Ingestion stores what the API said. This module turns that into the schema the
calculation layer reads, and it is where every source-specific quirk is spent so
that nothing downstream has to know MSPD exists.

Three of those quirks change the numbers rather than the plumbing:

**Security classes were renamed mid-history.** TIPS are published as a single
"Treasury Inflation-Protected Securities" row only from 2004-06. Before that they
are two rows, "Inflation-Indexed Notes" and "Inflation-Indexed Bonds". A mapping
keyed on the modern label alone drops every TIPS observation before 2004-06 —
silently, because the remaining classes still form a tidy series. Both legacy
labels therefore map to TIPS and are summed, which reproduces a continuous series
across the transition (2004-05: 152,777.4 + 46,953.7 = 199,731.1 against
200,390.9 the following month).

**Amounts are in millions.** They are converted to single currency units here, so
no downstream code has to remember which endpoint reports what. `debt_to_penny`
reports whole dollars while MSPD reports millions, and those two are compared
directly in the validation layer.

**TIPS amounts include inflation accretion.** Table 1's TIPS figure matches Table
3's inflation-adjusted total, not its par total, so `amount_basis` records
`INFLATION_ADJUSTED` for TIPS and `PAR` for everything else. Net issuance derived
from deltas of this column is accretion-contaminated for TIPS specifically, which
is why the issuance calculations exclude TIPS from the coupon aggregate by
default (Deviation D2).

An unrecognised class label raises. It is the one response that cannot produce a
wrong number: a label this module has never seen is either a new instrument or
another rename, and both need a human decision rather than a default.
"""

from __future__ import annotations

import pandas as pd

# Component labels observed across the full 2001-01 → 2026-07 history.
SECURITY_CLASS_MAP = {
    "Bills": "BILLS",
    "Notes": "NOTES",
    "Bonds": "BONDS",
    "Treasury Inflation-Protected Securities": "TIPS",   # 2004-06 onward
    "Inflation-Indexed Notes": "TIPS",                   # through 2004-05
    "Inflation-Indexed Bonds": "TIPS",                   # through 2004-05
    "Floating Rate Notes": "FRN",                        # 2014-01 onward
    "Federal Financing Bank": "OTHER",
}

# Total rows carry their label in `security_type_desc`, with `security_class_desc`
# set to the literal string "_". Only the marketable total is taken; the
# nonmarketable and grand totals are out of scope for this table.
TOTAL_TYPE_MAP = {"Total Marketable": "TOTAL_MARKETABLE"}

COMPONENT_TYPE = "Marketable"

# Classes whose published amount includes inflation accretion rather than par.
INFLATION_ADJUSTED_CLASSES = frozenset({"TIPS"})

MILLIONS = 1_000_000


class NormalizationError(ValueError):
    """The source contains something this module has no defined handling for."""


def normalize_debt_outstanding(
    typed: pd.DataFrame,
    *,
    country: str = "US",
    currency: str = "USD",
    source: str = "fiscaldata/mspd_table_1",
    retrieval_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build the `debt_outstanding` long table from a typed mspd_table_1 frame.

    Returns one row per (observation_date, security_class), with the published
    TOTAL_MARKETABLE carried as its own row rather than derived by summing the
    components — which is what keeps the reconciliation check meaningful.
    """
    required = {"record_date", "security_type_desc", "security_class_desc", "total_mil_amt"}
    missing = sorted(required - set(typed.columns))
    if missing:
        raise NormalizationError(f"mspd_table_1 frame is missing {missing}")

    df = typed.copy()
    df["security_type_desc"] = df["security_type_desc"].astype(str)
    df["security_class_desc"] = df["security_class_desc"].astype(str)

    components = df[df["security_type_desc"] == COMPONENT_TYPE].copy()
    unknown = sorted(set(components["security_class_desc"]) - set(SECURITY_CLASS_MAP))
    if unknown:
        first_seen = {
            label: str(components.loc[
                components["security_class_desc"] == label, "record_date"
            ].min())[:10]
            for label in unknown
        }
        raise NormalizationError(
            f"unmapped marketable security class(es) {unknown} (first seen "
            f"{first_seen}). MSPD has renamed a class or introduced an instrument; "
            "add it to SECURITY_CLASS_MAP deliberately rather than letting it drop "
            "out of the totals."
        )
    components["security_class"] = components["security_class_desc"].map(SECURITY_CLASS_MAP)

    totals = df[df["security_type_desc"].isin(TOTAL_TYPE_MAP)].copy()
    totals["security_class"] = totals["security_type_desc"].map(TOTAL_TYPE_MAP)

    stacked = pd.concat([components, totals], ignore_index=True)

    # Sum within (date, class): the only genuine duplicate is the pre-2004 pair of
    # inflation-indexed rows that both map to TIPS. min_count=1 keeps an all-NaN
    # group as NaN rather than turning it into a fabricated zero.
    grouped = (
        stacked.groupby(["record_date", "security_class"], observed=True, dropna=False)[
            "total_mil_amt"
        ]
        .sum(min_count=1)
        .reset_index()
    )

    out = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(grouped["record_date"]),
            # MSPD for month end M is not published until roughly the eighth
            # business day of M+1, but the endpoint does not carry that date. It
            # is left missing rather than estimated (Deviation D4): a derived
            # publication date would be indistinguishable from a reported one.
            "publication_date": pd.NaT,
            "country": country,
            "security_class": grouped["security_class"].astype("category"),
            "amount_outstanding": grouped["total_mil_amt"] * MILLIONS,
            "amount_basis": [
                "INFLATION_ADJUSTED" if c in INFLATION_ADJUSTED_CLASSES else "PAR"
                for c in grouped["security_class"]
            ],
            "currency": currency,
            "source": source,
        }
    )
    out["amount_basis"] = out["amount_basis"].astype("category")
    out["retrieval_date"] = pd.Timestamp(retrieval_date) if retrieval_date is not None else pd.NaT

    return out.sort_values(["observation_date", "security_class"]).reset_index(drop=True)
