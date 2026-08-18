"""Auction results with rolling statistics and the per-auction stress score."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from _shared import ACCENT, GRID, MUTED, WARM, kpi, load, page, provenance, require, style

page("Auctions")
st.title("Auctions")
st.caption(
    "Higher stress means weaker absorption. Each auction is scored against the "
    "trailing twelve auctions of the SAME tenor — a 30-year and a 2-year are not "
    "comparable on any of these measures."
)

if not require("auctions"):
    st.stop()

auctions = load("auctions")
held = auctions[auctions["has_results"]].copy()
scored = held[held["stress_score"].notna()].copy()

c1, c2, c3, c4 = st.columns(4)
kpi(c1, "Auctions in store", f"{len(held):,}",
    note=f"{held.auction_date.min():%Y-%m} → {held.auction_date.max():%Y-%m}")
kpi(c2, "Scored", f"{len(scored):,}",
    note=f"{len(held) - len(scored):,} awaiting a full trailing window")
kpi(c3, "Tenors", f"{scored['term'].nunique()}",
    note="scored against their own trailing 12")
if len(scored):
    latest = scored.sort_values("auction_date").iloc[-1]
    kpi(c4, "Latest scored auction", f"{latest.stress_score:+.0f}",
        note=f"{latest.term} on {latest.auction_date:%Y-%m-%d}")

st.divider()

tenors = sorted(
    scored["term"].dropna().unique(),
    key=lambda t: (t[-1], int(t[:-1])),
)
default = [t for t in ("10Y", "20Y", "30Y") if t in tenors] or tenors[:3]
chosen = st.multiselect("Tenors", tenors, default=default)

view = scored[scored["term"].isin(chosen)].sort_values("auction_date")

if len(view):
    st.markdown("##### Stress score by auction")
    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    for term in chosen:
        sub = view[view["term"] == term]
        fig.add_trace(go.Scatter(x=sub["auction_date"], y=sub["stress_score"],
                                 mode="markers", name=term, marker=dict(size=5)))
    st.plotly_chart(style(fig, ytitle="stress score"), use_container_width=True)

    st.markdown("##### Components against their trailing averages")
    metric = st.selectbox(
        "Measure",
        ["bid_to_cover", "indirect_pct", "primary_dealer_pct",
         "dispersion_bps", "allotment_at_high_pct"],
        format_func=lambda c: {
            "bid_to_cover": "Bid to cover",
            "indirect_pct": "Indirect share",
            "primary_dealer_pct": "Primary dealer takedown",
            "dispersion_bps": "High minus median yield (bps)",
            "allotment_at_high_pct": "Allotment at the high (%)",
        }[c],
    )
    fig2 = go.Figure()
    for term in chosen:
        sub = view[view["term"] == term]
        fig2.add_trace(go.Scatter(x=sub["auction_date"], y=sub[metric],
                                  mode="lines+markers", name=term,
                                  line=dict(width=1), marker=dict(size=4)))
    st.plotly_chart(style(fig2), use_container_width=True)

    st.markdown("##### Most recent auctions")
    columns = ["auction_date", "term", "security_type", "amount_accepted",
               "bid_to_cover", "indirect_pct", "primary_dealer_pct",
               "dispersion_bps", "allotment_at_high_pct", "stress_score"]
    table = view.sort_values("auction_date", ascending=False)[columns].head(40).copy()
    table["amount_accepted"] = (table["amount_accepted"] / 1e9).round(1)
    for col in ("indirect_pct", "primary_dealer_pct"):
        table[col] = (table[col] * 100).round(1)
    st.dataframe(
        table.rename(columns={"amount_accepted": "accepted $bn",
                              "indirect_pct": "indirect %",
                              "primary_dealer_pct": "dealer %",
                              "dispersion_bps": "high-median bps",
                              "allotment_at_high_pct": "allot at high %"}),
        use_container_width=True, hide_index=True,
    )

st.caption(
    "Bidder shares are fractions of COMPETITIVE accepted, not of total accepted. "
    "The total also contains SOMA add-ons, which reached 37% of an auction in "
    "2020-21; dividing by it would depress dealer and indirect shares in exactly "
    "the QE years and read as weakening private demand."
)

st.caption(
    "The processed store holds auctions from 2008-04, the first with a "
    "bidder-class breakdown. Earlier auctions back to 1979 are ingested and "
    "archived in `data/raw` but not scored: before about 2000 Treasury did not "
    "publish bid-to-cover at all, and scoring a reduced factor set as though it "
    "were the full one would make those auctions look comparable when they are "
    "not. The Data Quality page records how many are held back."
)

provenance("auctions")
