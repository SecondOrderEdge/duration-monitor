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

import re

import numpy as np
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


# --------------------------------------------------------------------------- #
# securities detail (WAM input)
# --------------------------------------------------------------------------- #

# Table 3 uses its own class labels, and renames TIPS on the same date Table 1
# does. Bills are reported at maturity value, which is their par.
DETAIL_CLASS_MAP = {
    "Bills Maturity Value": "BILLS",
    "Notes": "NOTES",
    "Bonds": "BONDS",
    "Inflation-Protected Securities": "TIPS",    # 2004-06 onward
    "Inflation-Indexed Notes": "TIPS",           # through 2004-05
    "Inflation-Indexed Bonds": "TIPS",           # through 2004-05
    "Floating Rate Notes": "FRN",
}


def normalize_securities_detail(
    typed: pd.DataFrame,
    *,
    country: str = "US",
    currency: str = "USD",
    source: str = "fiscaldata/mspd_table_3_market",
    retrieval_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build the security-level table that WAM is computed from.

    Two aggregations happen here, and getting either wrong changes the numbers
    while leaving a well-formed table behind.

    **Rows are tranches, not securities.** A reopened security has one row per
    reopening. `outstanding_amt` is populated on one row per reporting block and
    holds that block's total; the other rows carry only their own `issued_amt`.
    Rows are therefore grouped to one row per (date, CUSIP), summing the populated
    outstanding amounts. Fourteen (date, CUSIP) groups across the history are
    reported as two blocks rather than one, so this is a sum and not a "take the
    first populated value" — the latter silently loses a block.

    **Accretion is per tranche while outstanding is per block.** Subtracting
    `inflation_adj_amt` from `outstanding_amt` on the same row removes only that
    one tranche's accretion. For CUSIP 912828WU0 at 2024-06-30 that yields a par
    of 49,325 against the true 41,005 — a 20% overstatement. Accretion is summed
    across the security's rows first, and the result cross-checks exactly against
    the independent Σ(issued) + Σ(redeemed).

    Subtotal rows are excluded by requiring a non-null `maturity_date`, which is
    what distinguishes a security from a "Total Treasury Notes" label sitting in
    the same CUSIP column.
    """
    required = {
        "record_date", "security_class1_desc", "security_class2_desc",
        "maturity_date", "issue_date", "outstanding_amt", "inflation_adj_amt",
    }
    missing = sorted(required - set(typed.columns))
    if missing:
        raise NormalizationError(f"mspd_table_3_market frame is missing {missing}")

    df = typed.copy()
    df["security_class1_desc"] = df["security_class1_desc"].astype(str)

    # A null maturity_date marks a subtotal row ("Total Unmatured Treasury Notes",
    # "Total Marketable", Federal Financing Bank).
    df = df[df["maturity_date"].notna()].copy()

    unknown = sorted(set(df["security_class1_desc"]) - set(DETAIL_CLASS_MAP))
    if unknown:
        raise NormalizationError(
            f"unmapped security class(es) in mspd_table_3_market: {unknown}. Add "
            "them to DETAIL_CLASS_MAP deliberately rather than dropping them from "
            "the WAM universe."
        )

    df["security_class"] = df["security_class1_desc"].map(DETAIL_CLASS_MAP)
    df["cusip"] = df["security_class2_desc"].astype(str)

    keys = ["record_date", "cusip"]
    for col, label in (("maturity_date", "maturity date"), ("security_class", "class")):
        spread = df.groupby(keys, observed=True)[col].nunique(dropna=False)
        if (spread > 1).any():
            offenders = spread[spread > 1].head(3).index.tolist()
            raise NormalizationError(
                f"inconsistent {label} within a (date, CUSIP) group, e.g. {offenders}; "
                "these rows are not tranches of one security"
            )

    grouped = df.groupby(keys, observed=True)
    out = pd.DataFrame(
        {
            "amount_outstanding": grouped["outstanding_amt"].sum(min_count=1),
            "accretion": grouped["inflation_adj_amt"].sum(min_count=1).fillna(0.0),
            "maturity_date": grouped["maturity_date"].max(),
            "issue_date": grouped["issue_date"].min(),
            "security_class": grouped["security_class"].first(),
            "interest_rate": grouped["interest_rate_pct"].first()
            if "interest_rate_pct" in df.columns
            else pd.NA,
        }
    ).reset_index()

    # Par is the consistent weighting basis: TIPS are published inflation-adjusted
    # and every other class at par, so weighting them together on the published
    # figure weights TIPS by their accretion too (Deviation D9(b)).
    out["amount_par"] = out["amount_outstanding"] - out["accretion"]
    for col in ("amount_outstanding", "accretion", "amount_par"):
        out[col] = out[col] * MILLIONS

    out = out.rename(columns={"record_date": "observation_date"})
    out["country"] = country
    out["currency"] = currency
    out["amount_basis"] = "PAR"          # refers to amount_par, the WAM weight
    out["source"] = source
    out["retrieval_date"] = (
        pd.Timestamp(retrieval_date) if retrieval_date is not None else pd.NaT
    )

    return out.sort_values(["observation_date", "cusip"]).reset_index(drop=True)


def wam_input(securities: pd.DataFrame, *, basis: str = "PAR") -> pd.DataFrame:
    """Present the securities table to the WAM calculation on one weighting basis.

    `weighted_average_maturity` weights by `amount_outstanding` and refuses a frame
    with mixed `amount_basis`, which is the guard that makes this explicit rather
    than incidental: the caller has to say which basis it wants, and the answer
    differs by roughly the accretion share of TIPS.
    """
    if basis not in {"PAR", "INFLATION_ADJUSTED"}:
        raise NormalizationError(
            f"unknown weighting basis {basis!r}; expected PAR or INFLATION_ADJUSTED"
        )
    column = "amount_par" if basis == "PAR" else "amount_outstanding"

    out = securities.copy()
    out["amount_outstanding"] = out[column]
    out["amount_basis"] = basis
    return out


# --------------------------------------------------------------------------- #
# auctions
# --------------------------------------------------------------------------- #

_TERM_RE = re.compile(
    r"^(?:(?P<years>\d+)-Year)?\s*(?:(?P<months>\d+)-Month)?\s*"
    r"(?:(?P<weeks>\d+)-Week)?\s*(?:(?P<days>\d+)-Day)?$"
)

# Tenors the auction stress score is computed per. Anything else is carried with
# its parsed label and simply never matches the long-end set.
COUPON_TENORS = frozenset({"2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"})

BPS_PER_PERCENT = 100.0


def normalize_term(label: str) -> str | None:
    """Canonical tenor from an `original_security_term` label.

    Treasury writes the ORIGINAL term as "10-Year" and the REMAINING term as
    "9-Year 11-Month", so a reopened 10-year note carries both. Grouping on the
    remaining term scatters one tenor's history across a dozen labels and leaves
    the trailing-window comparison with nothing to compare against — which is why
    the canonical tenor is taken from the original term.

    A term with a months component is rounded to the nearest year (the two
    "29-Year 9-Month" bonds in the history are 30-year issues), and bills keep
    their week or day label.
    """
    # pandas 3 keeps NaN as NaN through .astype(str) rather than rendering it
    # "nan", so a non-string can reach here from any column with missing values.
    if label is None or not isinstance(label, str):
        return None
    if not label or label.strip().lower() in {"nan", "none", "null", ""}:
        return None

    match = _TERM_RE.match(label.strip())
    if not match:
        return None
    parts = {k: int(v) for k, v in match.groupdict().items() if v}
    if not parts:
        return None

    if "years" in parts or "months" in parts:
        years = parts.get("years", 0) + parts.get("months", 0) / 12
        return f"{round(years):g}Y"
    if "weeks" in parts:
        return f"{parts['weeks']}W"
    return f"{parts['days']}D"


def normalize_auctions(
    typed: pd.DataFrame,
    *,
    country: str = "US",
    currency: str = "USD",
    source: str = "fiscaldata/auctions_query",
    retrieval_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build the `auctions` table from a typed auctions_query frame.

    Announced-but-unheld auctions are dropped, but ONLY those. The endpoint
    publishes the forward calendar alongside results, so the last few rows by date
    are auctions that have not happened and carry nulls for every result field.

    The tempting test — drop any row with a null `bid_to_cover_ratio` — is wrong,
    and wrong in a way that looks tidy: bid-to-cover was not published at all
    before about 2000 (0% of auctions in the 1980s, 2% in the 1990s), so that test
    discards 3,215 genuine auctions and silently truncates the history to 1994
    while leaving a clean-looking series behind. Only five rows in the whole
    history are actually unheld.

    So the future calendar is removed by date, and a held auction with unreported
    results keeps its row with `has_results` False. Consumers that need a "latest
    auction" reading filter on `has_results` rather than taking the last row; the
    stress score naturally returns NaN where its inputs are absent.

    Bid dispersion uses the published median (Deviation D3) rather than the
    constant-maturity proxy. Bills are excluded from it by construction: they are
    auctioned on a discount basis and carry no yield fields at all.
    """
    required = {
        "auction_date", "security_type", "original_security_term", "total_accepted",
        "bid_to_cover_ratio", "high_yield", "avg_med_yield", "allocation_pctage",
        "primary_dealer_accepted", "indirect_bidder_accepted", "direct_bidder_accepted",
    }
    missing = sorted(required - set(typed.columns))
    if missing:
        raise NormalizationError(f"auctions_query frame is missing {missing}")

    df = typed.copy()

    # Not yet held: the auction date has not arrived. Anything on or before the
    # retrieval date happened, whether or not its results were ever published.
    as_of = pd.Timestamp(retrieval_date).tz_localize(None) if retrieval_date is not None \
        else pd.Timestamp.now("UTC").tz_localize(None)
    scheduled = pd.to_datetime(df["auction_date"]) > as_of
    n_unheld = int(scheduled.sum())
    df = df[~scheduled].copy()

    df["term"] = df["original_security_term"].astype(str).map(normalize_term)

    # Bidder shares are fractions of COMPETITIVE accepted, not of total accepted.
    # `total_accepted` also contains SOMA add-ons, FIMA noncompetitive and retail,
    # which are not competitive bidder classes. SOMA alone reached 37% of an
    # auction in 2020-21, so dividing by the total would depress dealer and
    # indirect shares in precisely the QE years and feed that artefact into the
    # stress score as if it were weakening demand. On the competitive base the
    # three classes sum to 1.0000 across every auction with results.
    competitive = df["comp_accepted"].where(df["comp_accepted"] > 0)
    fallback = df["total_accepted"].where(df["total_accepted"] > 0)
    accepted = competitive.fillna(fallback)
    out = pd.DataFrame(
        {
            "auction_date": pd.to_datetime(df["auction_date"]),
            "issue_date": pd.to_datetime(df.get("issue_date")),
            "maturity_date": pd.to_datetime(df.get("maturity_date")),
            "country": country,
            "security_type": df["security_type"].astype(str),
            "term": df["term"],
            "cusip": df.get("cusip"),
            "amount_offered": df.get("offering_amt"),
            "amount_accepted": df["total_accepted"],
            "amount_accepted_competitive": df["comp_accepted"],
            "soma_add_on": df.get("soma_accepted"),
            "bid_to_cover": df["bid_to_cover_ratio"],
            "high_yield": df["high_yield"],
            "median_yield": df["avg_med_yield"],
            "primary_dealer_pct": df["primary_dealer_accepted"] / accepted,
            "direct_pct": df["direct_bidder_accepted"] / accepted,
            "indirect_pct": df["indirect_bidder_accepted"] / accepted,
            "allotment_at_high_pct": df["allocation_pctage"],
        }
    )

    # The genuine dispersion measure: how far past the median the auction had to
    # reach to clear. Null wherever either yield is absent, which is every bill.
    out["dispersion_bps"] = (out["high_yield"] - out["median_yield"]) * BPS_PER_PERCENT
    out["tail_proxy_bps"] = pd.NA            # CMT diagnostic, not yet computed
    out["tail_proxy_method"] = "high_minus_published_median"
    out.loc[out["dispersion_bps"].isna(), "tail_proxy_method"] = "unavailable"

    # Results were not published for every auction that took place. That is a
    # documented gap in the source, not a reason to drop the auction.
    out["has_results"] = df["bid_to_cover_ratio"].notna().values
    # 0.9% of auctions have no competitive figure; those fall back to the total
    # and the substitution is recorded rather than assumed away.
    out["bidder_share_basis"] = np.where(
        competitive.notna().values, "competitive", "total_accepted"
    )

    out["currency"] = currency
    out["source"] = source
    out["retrieval_date"] = (
        pd.Timestamp(retrieval_date) if retrieval_date is not None else pd.NaT
    )
    out.attrs["n_unheld_dropped"] = n_unheld
    out.attrs["n_without_results"] = int((~out["has_results"]).sum())

    return out.sort_values("auction_date").reset_index(drop=True)
