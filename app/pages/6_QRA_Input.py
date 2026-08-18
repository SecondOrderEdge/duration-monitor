"""Quarterly Refunding Announcement manual entry.

No API exists for the QRA, and Phase 1 deliberately does not attempt to
NLP-extract the PDFs. This is the entry point for facts read off the official
documents by hand, and every row must cite the document it came from — an
unsourced row here is indistinguishable from a fabricated one.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import streamlit as st

from _shared import REPO_ROOT, page

page("QRA input")
st.title("Quarterly Refunding Announcement")
st.caption(
    "Manual entry. Every row carries the URL of the Treasury document it was read "
    "from, validated non-empty at entry."
)

LOG = REPO_ROOT / "data" / "manual" / "qra_log.csv"
COLUMNS = [
    "announcement_date", "quarter", "projected_borrowing_current_q",
    "projected_borrowing_next_q", "projected_eoq_cash_balance",
    "expected_bill_issuance", "expected_coupon_issuance",
    "coupon_auction_size_changes", "commentary_bills", "commentary_coupons",
    "commentary_duration", "commentary_demand", "source_url", "entered_by",
    "entered_date",
]


def load_log() -> pd.DataFrame:
    if LOG.exists():
        return pd.read_csv(LOG)
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})


existing = load_log()

st.markdown(f"##### {len(existing)} entr{'y' if len(existing) == 1 else 'ies'} recorded")
if len(existing):
    st.dataframe(existing.tail(8), use_container_width=True, hide_index=True)

st.divider()
st.markdown("##### Add an entry")

with st.form("qra_entry", clear_on_submit=False):
    c1, c2 = st.columns(2)
    with c1:
        announcement_date = st.date_input("Announcement date")
        quarter = st.text_input("Quarter", placeholder="2026Q3")
        borrow_current = st.number_input("Projected borrowing, current quarter ($bn)",
                                         value=0.0, step=10.0)
        borrow_next = st.number_input("Projected borrowing, next quarter ($bn)",
                                      value=0.0, step=10.0)
        cash_balance = st.number_input("Projected end-of-quarter cash balance ($bn)",
                                       value=0.0, step=10.0)
    with c2:
        bill_issuance = st.number_input("Expected bill issuance ($bn)",
                                        value=0.0, step=10.0)
        coupon_issuance = st.number_input("Expected coupon issuance ($bn)",
                                          value=0.0, step=10.0)
        size_changes = st.text_area("Coupon auction size changes", height=80)
        entered_by = st.text_input("Entered by")

    source_url = st.text_input(
        "Source URL (required)",
        placeholder="https://home.treasury.gov/news/press-releases/...",
    )
    st.caption("Must point at the official Treasury document this row was read from.")

    c3, c4 = st.columns(2)
    with c3:
        commentary_bills = st.text_area("Commentary — bills", height=90)
        commentary_coupons = st.text_area("Commentary — coupons", height=90)
    with c4:
        commentary_duration = st.text_area("Commentary — duration", height=90)
        commentary_demand = st.text_area("Commentary — demand", height=90)

    submitted = st.form_submit_button("Add entry")

if submitted:
    problems = []
    if not source_url.strip():
        problems.append("Source URL is required — an unsourced row cannot be published.")
    elif not source_url.strip().lower().startswith(("http://", "https://")):
        problems.append("Source URL must be a link to the official document.")
    if not quarter.strip():
        problems.append("Quarter is required.")
    if not entered_by.strip():
        problems.append("Entered by is required.")
    if len(existing) and quarter.strip() in set(existing.get("quarter", [])):
        problems.append(f"{quarter.strip()} already has an entry — edit the CSV instead "
                        "of adding a duplicate.")

    if problems:
        for problem in problems:
            st.error(problem)
    else:
        row = {
            "announcement_date": str(announcement_date),
            "quarter": quarter.strip(),
            "projected_borrowing_current_q": borrow_current,
            "projected_borrowing_next_q": borrow_next,
            "projected_eoq_cash_balance": cash_balance,
            "expected_bill_issuance": bill_issuance,
            "expected_coupon_issuance": coupon_issuance,
            "coupon_auction_size_changes": size_changes.strip(),
            "commentary_bills": commentary_bills.strip(),
            "commentary_coupons": commentary_coupons.strip(),
            "commentary_duration": commentary_duration.strip(),
            "commentary_demand": commentary_demand.strip(),
            "source_url": source_url.strip(),
            "entered_by": entered_by.strip(),
            "entered_date": str(pd.Timestamp.now("UTC").date()),
        }
        LOG.parent.mkdir(parents=True, exist_ok=True)
        pd.concat([existing, pd.DataFrame([row])], ignore_index=True)[COLUMNS].to_csv(
            LOG, index=False
        )
        st.success(f"Recorded {row['quarter']}. Commit `{LOG.relative_to(REPO_ROOT)}`.")
        st.rerun()

st.info(
    "Amounts are entered in **billions**, as the QRA states them. The processed "
    "store holds single currency units elsewhere; this file is the one place the "
    "published unit is kept, because it is transcribed by hand from a document "
    "that uses it."
)
