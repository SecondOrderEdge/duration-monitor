"""What Treasury executed — the genuinely current part of the monitor.

The score runs at MSPD's speed: monthly, published four business days after
month-end, so it is structurally three to seven weeks behind and can never say
what Treasury is doing TODAY. Operations can. Auction results publish the day of
the auction and buyback results the day of the operation, so this page answers
"what did Treasury actually execute" from primary data that is days old, while
the score answers "what has that added up to" a month in arrears.

Buybacks matter here twice over: they are the freshest revealed-behaviour signal,
and unadjusted they CONTAMINATE the score — MSPD deltas net retired securities
into "issuance", so a coupon buyback reads as coupon restraint. The score is
buyback-adjusted (config `issuance.buyback_adjustment`); this page shows the
operations behind that adjustment.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from _shared import ACCENT, MUTED, kpi, load, page, provenance, require

page("Operations")
st.title("Operations")
st.caption(
    "Executed auctions and buybacks, days old — against a score that is monthly "
    "by construction. Two speeds, one monitor."
)

if not require("buybacks", "auctions"):
    st.stop()

buybacks = load("buybacks")
buybacks["operation_date"] = pd.to_datetime(buybacks["operation_date"])
auctions = load("auctions")
auctions["auction_date"] = pd.to_datetime(auctions["auction_date"])

today = pd.Timestamp.today().normalize()
recent_bb = buybacks[buybacks.operation_date >= today - pd.Timedelta(days=45)]
recent_au = auctions[(auctions.auction_date >= today - pd.Timedelta(days=14))
                     & (auctions.auction_date <= today)]

c1, c2, c3, c4 = st.columns(4)
kpi(c1, "Buyback ops, 45d", str(len(recent_bb)),
    note=f"${recent_bb.par_accepted.sum()/1e9:.1f}bn par retired")
kpi(c2, "Auctions, 14d", str(len(recent_au)),
    note=f"latest {auctions.auction_date.max():%Y-%m-%d}")
kpi(c3, "Latest buyback", f"{buybacks.operation_date.max():%m-%d}",
    note=str(buybacks.sort_values('operation_date').maturity_bucket.iloc[-1]))
kpi(c4, "Program total", f"${buybacks.par_accepted.sum()/1e9:.0f}bn",
    note=f"since {buybacks.operation_date.min():%Y}")

st.divider()
st.subheader("Recent buyback operations")
show = buybacks.sort_values("operation_date", ascending=False).head(12).copy()
show["offered $bn"] = (show.total_par_amt_offered / 1e9).round(2)
show["accepted $bn"] = (show.par_accepted / 1e9).round(2)
show["max $bn"] = (pd.to_numeric(show.max_par_amt_redeemed, errors="coerce") / 1e9).round(1)
st.dataframe(
    show[["operation_date", "operation_type", "security_class", "maturity_bucket",
          "offered $bn", "accepted $bn", "max $bn"]],
    hide_index=True, width="stretch",
)
st.caption(
    "Buybacks are ANNOUNCED in advance — schedule, buckets and maximums are "
    "published with the quarterly refunding. There is nothing to predict; there "
    "is something to read. Offered far above accepted is normal: dealers offer, "
    "Treasury takes up to the announced maximum."
)

st.subheader("Recent auctions")
if len(recent_au):
    # Explicit columns, no existence filter: a renamed upstream column should
    # break this page loudly, not quietly shrink the table.
    show_au = recent_au.sort_values("auction_date", ascending=False).copy()
    show_au["offered $bn"] = (show_au.amount_offered / 1e9).round(1)
    show_au["accepted $bn"] = (show_au.amount_accepted / 1e9).round(1)
    st.dataframe(
        show_au[["auction_date", "term", "security_type", "offered $bn",
                 "accepted $bn", "bid_to_cover", "indirect_pct"]],
        hide_index=True, width="stretch",
    )
else:
    st.info("No auctions in the last 14 days.")

st.divider()
st.markdown(
    "##### Reading this against the score\n"
    "The score's quantity factors cannot be fresher than MSPD — monthly, "
    "published ~4 business days after month-end. **A 3-7 week lag on the stock "
    "is permanent and structural.** This page is the flow: what Treasury sold "
    "and retired this week. The score then confirms, a month later, what the "
    "flows added up to. Neither is a trading signal — the backtest "
    "(`docs/backtest.md`) found no reliable forward information in the score, "
    "and operations are announced before they happen."
)

provenance("buybacks", observation=f"{buybacks.operation_date.max():%Y-%m-%d}")
