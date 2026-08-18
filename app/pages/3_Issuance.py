"""Issuance detail: bill share, net issuance by class, and the funding ratios."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from _shared import ACCENT, MUTED, SERIES, WARM, kpi, load, page, provenance, require, style

from src import config
from src.calculations.issuance import (
    aggregate_net_issuance,
    bill_share,
    bill_share_changes,
    bill_to_coupon_ratio,
    incremental_bill_funding,
    net_issuance,
)

page("Issuance")
st.title("Issuance")
st.caption(
    "Direction of travel, not level. The question is whether the MARGINAL deficit "
    "is being financed with bills."
)

if not require("debt_outstanding"):
    st.stop()

debt = load("debt_outstanding")
share = bill_share(debt)
changes = bill_share_changes(share, horizons=(3, 6, 12))
net = net_issuance(debt)
floor = config.min_abs_denominator("M")
funding = incremental_bill_funding(net, min_abs_denominator=floor)
ratio = bill_to_coupon_ratio(net, min_abs_denominator=floor)

c1, c2, c3, c4 = st.columns(4)
kpi(c1, "Bill share", f"{share.iloc[-1]:.1%}", note=f"as at {share.index[-1]}")
for col, horizon in ((c2, 3), (c3, 6), (c4, 12)):
    kpi(col, f"{horizon}m change", f"{changes[f'change_{horizon}m'].iloc[-1]:+.2%}",
        note="rising = shortening")

st.divider()

st.markdown("##### Bill share, with the TBAC reference band")
low, high = config.bill_share_reference_band()
x = share.index.to_timestamp()
fig = go.Figure()
fig.add_hrect(y0=low, y1=high, line_width=0, fillcolor=MUTED, opacity=0.12, layer="below")
fig.add_trace(go.Scatter(x=x, y=share.values, name="Bill share",
                         line=dict(color=ACCENT, width=2)))
fig.update_yaxes(tickformat=".0%")
st.plotly_chart(style(fig, ytitle="share of marketable"), use_container_width=True)

st.markdown("##### Net issuance by class")
freq = st.radio("Frequency", ["Quarterly", "Monthly"], horizontal=True)
flows = aggregate_net_issuance(net, freq="Q") if freq == "Quarterly" else net
pivot = (
    flows.pivot(index="period", columns="security_class", values="net_issuance")
    .drop(columns=["TOTAL_MARKETABLE"], errors="ignore")
)
window = 40 if freq == "Quarterly" else 120
recent = pivot.tail(window)

fig2 = go.Figure()
for cls in ["BILLS", "NOTES", "BONDS", "TIPS", "FRN", "OTHER"]:
    if cls in recent.columns:
        fig2.add_trace(go.Bar(x=recent.index.to_timestamp(), y=recent[cls] / 1e9,
                              name=cls.title(), marker_color=SERIES[cls]))
fig2.update_layout(barmode="relative")
st.plotly_chart(style(fig2, ytitle="$bn, net"), use_container_width=True)

st.markdown("##### Incremental bill funding")
st.caption(
    "Net bills as a share of net marketable borrowing. Periods where the "
    f"denominator is smaller than ${floor/1e9:,.0f}bn in absolute terms are left "
    "blank: during a binding debt ceiling net borrowing collapses toward zero and "
    "the ratio becomes unbounded, which would dominate any chart it appeared on "
    "(Deviation D5)."
)

series = funding["incremental_bill_funding"]
masked = funding["denominator_masked"]
fx = series.index.to_timestamp()
fig3 = go.Figure()
fig3.add_hline(y=0, line=dict(color=MUTED, width=1))
fig3.add_hline(y=1, line=dict(color=MUTED, width=1, dash="dot"))
for period in series.index[masked]:
    fig3.add_vrect(x0=period.to_timestamp(), x1=(period + 1).to_timestamp(),
                   line_width=0, fillcolor=MUTED, opacity=0.18, layer="below")
fig3.add_trace(go.Scatter(x=fx, y=series.values, name="Incremental bill funding",
                          line=dict(color=ACCENT, width=1.6), connectgaps=False))
fig3.update_yaxes(tickformat=".0%")
st.plotly_chart(style(fig3, ytitle="share of net borrowing"), use_container_width=True)
st.caption(
    f"{int(masked.sum())} of {len(masked)} months masked. Shaded bands are the "
    "masked periods, shown rather than hidden."
)

with st.expander("Bill-to-coupon ratio"):
    st.caption(
        "Signed and unbounded by nature: negative net coupon issuance alongside "
        "positive net bills is a genuine and highly relevant configuration, so the "
        "sign is preserved rather than clipped. Read alongside incremental bill "
        "funding, which is bounded."
    )
    rx = ratio.index.to_timestamp()
    fig4 = go.Figure()
    fig4.add_hline(y=0, line=dict(color=MUTED, width=1))
    fig4.add_trace(go.Scatter(x=rx, y=ratio["bill_to_coupon_ratio"].values,
                              line=dict(color=WARM, width=1.4), connectgaps=False,
                              name="Bill / coupon"))
    st.plotly_chart(style(fig4, ytitle="ratio"), use_container_width=True)

st.caption(
    f"Coupon aggregate excludes TIPS ({funding['coupon_classes'].iloc[0]}). "
    "Month-over-month change in TIPS outstanding includes inflation accretion, so "
    "including it would inflate the coupon denominator during high-inflation "
    "periods and understate incremental bill funding — a bias that runs against "
    "the thesis being tested (Deviation D2)."
)

provenance("debt_outstanding", observation=str(share.index[-1]))
