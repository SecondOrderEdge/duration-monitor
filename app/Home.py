"""Sovereign Debt Duration & Fiscal Liquidity Monitor — Home.

Reads `data/processed/` and nothing else. No API is called at page load, so the
page renders at the speed of a parquet read and a refresh outage degrades to
stale-but-labelled rather than a broken page.

Metrics that have no data yet are rendered as explicitly unavailable, never as a
blank or a zero. A KPI card showing "—" because ingestion has not been written is
honest; the same card showing 0.0 is a lie that looks like a reading.
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src import config  # noqa: E402
from src.calculations.issuance import (  # noqa: E402
    aggregate_net_issuance,
    bill_share,
    bill_share_changes,
    incremental_bill_funding,
    net_issuance,
)

PROCESSED = REPO_ROOT / "data" / "processed"

# Restrained institutional palette. Bills are the subject of the thesis and get
# the only saturated colour; everything else recedes.
INK = "#e6e9ef"
MUTED = "#8b93a7"
GRID = "#1e2330"
PAPER = "#0e1117"
ACCENT = "#4c9be8"
WARM = "#d98a4a"
SERIES = {"BILLS": ACCENT, "NOTES": "#5b6478", "BONDS": "#7d8799", "TIPS": "#9aa3b5",
          "FRN": "#4a5262", "OTHER": "#3a4150"}

st.set_page_config(
    page_title="Sovereign Duration Monitor",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------- #
# data access
# --------------------------------------------------------------------------- #

def _mtime(path: pathlib.Path) -> float:
    """Cache key. Rereads only when the pipeline has rewritten the file."""
    return path.stat().st_mtime


@st.cache_data(show_spinner=False)
def load_debt_outstanding(_mtime_key: float) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "debt_outstanding.parquet")


def processed_available(name: str) -> bool:
    return (PROCESSED / f"{name}.parquet").exists()


# --------------------------------------------------------------------------- #
# presentation helpers
# --------------------------------------------------------------------------- #

def kpi(col, label: str, value: str, delta: str | None = None,
        note: str | None = None, unavailable: bool = False) -> None:
    """One KPI card. `unavailable` renders an em dash and the reason."""
    with col:
        if unavailable:
            st.metric(label, "—")
            st.caption(note or "not yet ingested")
        else:
            st.metric(label, value, delta)
            if note:
                st.caption(note)


def style(fig: go.Figure, *, height: int = 380, ytitle: str = "") -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        font=dict(color=INK, size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11)),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False,
                     title=ytitle, tickfont=dict(color=MUTED))
    return fig


# --------------------------------------------------------------------------- #
# page
# --------------------------------------------------------------------------- #

st.title("Sovereign Debt Duration & Fiscal Liquidity Monitor")
st.caption(
    "Is the marginal deficit being financed with bills instead of duration, and is "
    "the sovereign deliberately shortening its financing profile? "
    "Level of debt is context; direction of travel is the signal."
)

if not processed_available("debt_outstanding"):
    st.error(
        "No processed data. Run `python scripts/refresh.py` to build "
        "`data/processed/` before launching the app."
    )
    st.stop()

path = PROCESSED / "debt_outstanding.parquet"
debt = load_debt_outstanding(_mtime(path))

share = bill_share(debt)
changes = bill_share_changes(share)
net = net_issuance(debt)
funding = incremental_bill_funding(net, min_abs_denominator=config.min_abs_denominator("M"))

latest_period = share.index[-1]
latest_share = share.iloc[-1]
change_12m = changes["change_12m"].iloc[-1]
retrieved = pd.to_datetime(debt["retrieval_date"].max())

band_low, band_high = config.bill_share_reference_band()

# ---- KPI row ------------------------------------------------------------- #
st.markdown(f"#### United States · data as of {latest_period}")

c1, c2, c3, c4 = st.columns(4)
kpi(c1, "Bill share of marketable", f"{latest_share:.1%}",
    note=f"TBAC reference band {band_low:.0%}–{band_high:.0%}")
kpi(c2, "1y change, bill share", f"{change_12m:+.1%}",
    note="rising = shortening")

recent = funding["incremental_bill_funding"].dropna()
if len(recent):
    kpi(c3, "Incremental bill funding", f"{recent.iloc[-1]:.0%}",
        note=f"latest unmasked period {recent.index[-1]}")
else:
    kpi(c3, "Incremental bill funding", "", unavailable=True,
        note="denominator masked in every period")

kpi(c4, "Weighted average maturity", "", unavailable=True,
    note="needs securities_detail ingestion (step 4)")

c5, c6, c7, c8 = st.columns(4)
kpi(c5, "10y term premium (ACM)", "", unavailable=True, note="needs NY Fed ingestion (step 5)")
kpi(c6, "Long-end auction stress", "", unavailable=True, note="needs auctions ingestion (step 6)")
kpi(c7, "Fiscal Duration Shift Score", "", unavailable=True, note="Phase 2")
kpi(c8, "Global score", "", unavailable=True, note="Phase 3")

st.divider()

# ---- Chart 1: bill share ------------------------------------------------- #
st.markdown("##### T-bill share of marketable debt")

x = share.index.to_timestamp()
fig = go.Figure()
fig.add_hrect(y0=band_low, y1=band_high, line_width=0,
              fillcolor=MUTED, opacity=0.12, layer="below")
fig.add_annotation(x=x[len(x) // 12], y=band_high, text="TBAC reference band",
                   showarrow=False, yshift=10, font=dict(color=MUTED, size=11))
fig.add_trace(go.Scatter(x=x, y=share.values, name="Bill share",
                         line=dict(color=ACCENT, width=2)))
fig.update_yaxes(tickformat=".0%")
st.plotly_chart(style(fig, ytitle="share of marketable"), use_container_width=True)

st.caption(
    f"Range {share.min():.1%} ({share.idxmin()}) to {share.max():.1%} ({share.idxmax()}). "
    "The 2020 move from 15.5% in March to 25.5% in June is the pandemic bill surge; "
    "the subsequent decline is the termining-out through 2021."
)

# ---- Chart 2: net issuance ------------------------------------------------ #
st.markdown("##### Net issuance by security class, quarterly")

# Net issuance is a flow, so quarterly means summing the monthly changes — not
# recomputing the change on a quarterly calendar, which would silently measure
# something else.
quarterly = aggregate_net_issuance(net, freq="Q")
pivot = quarterly.pivot(index="period", columns="security_class", values="net_issuance")
pivot = pivot.drop(columns=["TOTAL_MARKETABLE"], errors="ignore")

recent_q = pivot.loc[pivot.index >= pivot.index[-1] - 39]  # last ~10 years
qx = recent_q.index.to_timestamp()
voided = int(quarterly.loc[~quarterly["period_complete"], "period"].nunique())

fig2 = go.Figure()
for cls in ["BILLS", "NOTES", "BONDS", "TIPS", "FRN", "OTHER"]:
    if cls in recent_q.columns:
        fig2.add_trace(go.Bar(x=qx, y=recent_q[cls] / 1e9, name=cls.title(),
                              marker_color=SERIES[cls]))
fig2.update_layout(barmode="relative")
st.plotly_chart(style(fig2, ytitle="$bn, net"), use_container_width=True)

st.caption(
    "Month-over-month change in amount outstanding, summed to quarters. This "
    "approximates net issuance: MSPD deltas net issuance against redemptions "
    "within the period, and for TIPS they also absorb inflation accretion, which "
    "is why TIPS is excluded from the coupon aggregate in the funding ratios. "
    "Quarters missing a month are left blank rather than partially summed — the "
    "current quarter stays blank until its third month is published."
)

# ---- Chart 3+: not yet built --------------------------------------------- #
st.divider()
st.markdown("##### Not yet available")
st.info(
    "**WAM history** needs `securities_detail` ingestion · "
    "**10y term premium vs bill share** needs NY Fed ACM ingestion · "
    "**Long-end auction stress** needs auctions ingestion · "
    "**Global comparison** is Phase 3.\n\n"
    "The calculations for WAM and auction stress are written and tested; what is "
    "missing is the ingestion that feeds them."
)

with st.sidebar:
    st.markdown("### Provenance")
    st.write(f"**Observation** {latest_period}")
    st.write(f"**Retrieved** {retrieved:%Y-%m-%d %H:%M} UTC")
    st.caption(
        "MSPD for a given month end is not published until roughly the eighth "
        "business day of the following month. That publication date is not carried "
        "by the endpoint and is deliberately not estimated."
    )
    st.markdown("### Source")
    st.caption("Treasury Fiscal Data, `mspd_table_1`. Amounts converted from the "
               "published millions to single dollars on ingestion.")
    masked = int(funding["denominator_masked"].sum())
    st.markdown("### Data quality")
    st.write(f"{len(share)} monthly observations")
    st.write(f"{masked} period(s) with a masked funding ratio")
    st.caption("Masking is the debt-ceiling guard: no meaningful share of "
               "borrowing exists when there is no net borrowing to share.")
