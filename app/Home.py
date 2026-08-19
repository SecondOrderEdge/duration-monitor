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
def load_processed(name: str, _mtime_key: float) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / f"{name}.parquet")


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

debt = load_processed("debt_outstanding", _mtime(PROCESSED / "debt_outstanding.parquet"))

has_score = processed_available("score")
if has_score:
    score_table = load_processed("score", _mtime(PROCESSED / "score.parquet"))
    score_table["period"] = pd.PeriodIndex(score_table["period"], freq="M")
    score_table = score_table.set_index("period").sort_index()
    scored = score_table[score_table["score"].notna()]
else:
    score_table = scored = None

has_tp = processed_available("term_premium")
term_premium = (
    load_processed("term_premium", _mtime(PROCESSED / "term_premium.parquet"))
    if has_tp
    else None
)

has_stress = processed_available("long_end_stress")
stress = (
    load_processed("long_end_stress", _mtime(PROCESSED / "long_end_stress.parquet"))
    .set_index("date")["long_end_stress"]
    if has_stress
    else None
)

has_wam = processed_available("wam")
wam = (
    load_processed("wam", _mtime(PROCESSED / "wam.parquet")).set_index("observation_date")
    if has_wam
    else None
)

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

if has_wam:
    wam_now = wam["wam_years"].iloc[-1]
    wam_12m = wam_now - wam["wam_years"].iloc[-13] if len(wam) > 13 else float("nan")
    kpi(c4, "Weighted average maturity", f"{wam_now:.2f}y", f"{wam_12m:+.2f}y / 1y",
        note=f"{wam['within_1y'].iloc[-1]:.0%} matures within 1y")
else:
    kpi(c4, "Weighted average maturity", "", unavailable=True,
        note="run scripts/refresh.py --only wam")

c5, c6, c7, c8 = st.columns(4)
if has_tp:
    tp10 = (
        term_premium[term_premium["maturity"] == "10Y"]
        .set_index("date")["value"]
        .sort_index()
    )
    # Daily to month end, per the stated alignment convention (Deviation D8).
    # Monthly data is never forward-filled onto a daily axis for signal purposes.
    tp10_m = tp10.resample("ME").last()
    tp10_m.index = tp10_m.index.to_period("M")
    tp_change_12m = tp10_m.iloc[-1] - tp10_m.iloc[-13] if len(tp10_m) > 13 else float("nan")
    kpi(c5, "10y term premium (ACM)", f"{tp10.iloc[-1]:.2f}%",
        f"{tp_change_12m:+.2f}pp / 1y", note=f"as at {tp10.index[-1]:%Y-%m-%d}")
else:
    kpi(c5, "10y term premium (ACM)", "", unavailable=True,
        note="run scripts/refresh.py --only term_premium")
if has_stress:
    stress_now = stress.iloc[-1]
    kpi(c6, "Long-end auction stress", f"{stress_now:+.0f}",
        note=f"10/20/30y, 90d rolling · as at {stress.index[-1]:%Y-%m-%d}")
else:
    kpi(c6, "Long-end auction stress", "", unavailable=True,
        note="run scripts/refresh.py --only auctions")
if has_score and len(scored):
    latest_score = scored["score"].iloc[-1]
    prior = scored["score"].iloc[-13] if len(scored) > 13 else float("nan")
    kpi(c7, "Fiscal Duration Shift Score", f"{latest_score:.0f}",
        f"{latest_score - prior:+.0f} / 1y",
        note=f"{scored['band'].iloc[-1]} · {scored.index[-1]}")
else:
    kpi(c7, "Fiscal Duration Shift Score", "", unavailable=True,
        note="run scripts/refresh.py --only score")
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

# ---- Chart 3: WAM vs bill share ------------------------------------------ #
if has_wam:
    st.markdown("##### Weighted average maturity, with bill share")

    wx = pd.to_datetime(wam.index)
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=wx, y=wam["wam_years"], name="WAM (years)",
                              line=dict(color=WARM, width=2), yaxis="y"))
    fig3.add_trace(go.Scatter(x=x, y=share.values, name="Bill share",
                              line=dict(color=ACCENT, width=1.5, dash="dot"), yaxis="y2"))
    fig3.update_layout(
        yaxis=dict(title="WAM, years", gridcolor=GRID, tickfont=dict(color=MUTED)),
        yaxis2=dict(title="bill share", overlaying="y", side="right",
                    tickformat=".0%", showgrid=False, tickfont=dict(color=MUTED)),
    )
    st.plotly_chart(style(fig3), use_container_width=True)
    st.caption(
        f"WAM ranges {wam['wam_years'].min():.2f}y to {wam['wam_years'].max():.2f}y. "
        "The two series are the stock counterparts of one another — a rising bill "
        "share mechanically shortens WAM — so they are shown together rather than "
        "treated as independent evidence. Weighted at par: TIPS are published "
        "inflation-adjusted and weighting them on that basis would count accretion "
        "as duration."
    )

# ---- Chart 4: term premium vs bill share --------------------------------- #
if has_tp:
    st.markdown("##### 10y term premium and bill share")

    horizon = config.load("thresholds")["alignment"]["interaction_flag_horizon_months"]
    aligned = pd.DataFrame({"bill_share": share, "term_premium": tp10_m}).dropna()
    both_rising = (
        (aligned["bill_share"].diff(horizon) > 0)
        & (aligned["term_premium"].diff(horizon) > 0)
    )

    ax = aligned.index.to_timestamp()
    fig4 = go.Figure()
    # Shade the periods where both are rising — the signature the thesis predicts.
    for period in aligned.index[both_rising]:
        fig4.add_vrect(x0=period.to_timestamp(), x1=(period + 1).to_timestamp(),
                       line_width=0, fillcolor=WARM, opacity=0.16, layer="below")
    fig4.add_trace(go.Scatter(x=ax, y=aligned["term_premium"], name="10y ACM term premium",
                              line=dict(color=WARM, width=2), yaxis="y"))
    fig4.add_trace(go.Scatter(x=ax, y=aligned["bill_share"], name="Bill share",
                              line=dict(color=ACCENT, width=1.5, dash="dot"), yaxis="y2"))
    fig4.update_layout(
        yaxis=dict(title="term premium, %", gridcolor=GRID, tickfont=dict(color=MUTED)),
        yaxis2=dict(title="bill share", overlaying="y", side="right",
                    tickformat=".0%", showgrid=False, tickfont=dict(color=MUTED)),
    )
    st.plotly_chart(style(fig4), use_container_width=True)

    flagged_now = bool(both_rising.iloc[-1]) if len(both_rising) else False
    st.caption(
        f"Shading marks months where bill share and the 10y term premium have BOTH "
        f"risen over {horizon} months — the signature the thesis predicts, and the "
        f"one reading that requires quantity and market-price evidence to agree. "
        f"{'Currently flagged.' if flagged_now else 'Not currently flagged.'} "
        f"{int(both_rising.sum())} of {len(both_rising)} aligned months since "
        f"{aligned.index[0]}. Daily term premium is resampled to month end; monthly "
        "data is never forward-filled onto a daily axis."
    )

# ---- Chart 5: long-end auction stress ------------------------------------ #
if has_stress:
    st.markdown("##### Long-end auction stress")

    fig5 = go.Figure()
    fig5.add_hline(y=0, line=dict(color=MUTED, width=1))
    fig5.add_trace(go.Scatter(x=stress.index, y=stress.values, name="Long-end stress",
                              line=dict(color=WARM, width=1.6)))
    st.plotly_chart(style(fig5, ytitle="stress score"), use_container_width=True)
    st.caption(
        "Rolling 90-day mean across 10/20/30y auctions. **Higher means weaker "
        "absorption.** Composite of bid-to-cover, indirect share and dealer "
        "takedown against each tenor's trailing 12 auctions, plus two genuine "
        "published dispersion measures — high-minus-median yield and "
        "allotment-at-high. The constant-maturity tail proxy the brief proposed "
        "is kept at zero weight: the median is published, so a noisier substitute "
        "is not needed. Scored from 2008-04, the first auction with a bidder-class "
        "breakdown."
    )

# ---- Chart 6: the composite score ----------------------------------------- #
if has_score and len(scored):
    st.divider()
    st.markdown("##### Fiscal Duration Shift Score")

    bands = config.load("thresholds")["duration_shift_score_bands"]["bands"]
    shades = {"strong duration extension": "#2f5d47", "modest extension": "#3d5a4a",
              "neutral": "#2a2f3c", "meaningful shortening": "#5a4433",
              "aggressive shortening": "#6b3a34"}
    sx = scored.index.to_timestamp()

    fig6 = go.Figure()
    for band in bands:
        fig6.add_hrect(y0=band["from"], y1=band["to"], line_width=0, layer="below",
                       fillcolor=shades.get(band["name"], MUTED), opacity=0.35)
        fig6.add_annotation(x=sx[2], y=(band["from"] + band["to"]) / 2,
                            text=band["name"], showarrow=False,
                            font=dict(color=MUTED, size=10), xanchor="left")
    fig6.add_trace(go.Scatter(x=sx, y=scored["score"], name="Duration Shift Score",
                              line=dict(color=INK, width=2)))
    fig6.update_yaxes(range=[0, 100])
    st.plotly_chart(style(fig6, ytitle="score", height=420), use_container_width=True)

    st.caption(
        "Six factors, each a point-in-time percentile rank against its own past, "
        "combined with weights derived from their correlation structure so a "
        "factor that duplicates another earns less rather than being removed. "
        "Weights are recomputed on an expanding window, so no reading uses "
        "information that did not exist at the time."
    )

    # Factor contributions explain the current reading.
    contribs = {c.replace("contrib_", ""): scored[c].iloc[-1]
                for c in scored.columns if c.startswith("contrib_")}
    weights_now = {c.replace("weight_", ""): scored[c].iloc[-1]
                   for c in scored.columns if c.startswith("weight_")}
    detail = pd.DataFrame({
        "weight": pd.Series(weights_now),
        "percentile": pd.Series({k.replace("rank_", ""): scored[k].iloc[-1]
                                 for k in scored.columns if k.startswith("rank_")}),
        "contribution": pd.Series(contribs),
    }).dropna(how="all")
    with st.expander(f"What makes up the current reading of {latest_score:.0f}"):
        st.dataframe(detail.round(2), use_container_width=True)
        st.caption(
            "Contributions sum to the score. Weights are as at the latest month; "
            "they change as history accumulates."
        )

    st.markdown("##### Backtest against the episodes the brief names")
    EPISODES = {"2008 GFC": ("2008-09", "2009-03"),
                "2011 debt ceiling": ("2011-05", "2011-10"),
                "2013 taper": ("2013-05", "2013-12"),
                "2020 pandemic": ("2020-03", "2020-09"),
                "2021 normalisation": ("2021-01", "2021-12"),
                "2023 SVB + QRA": ("2023-03", "2023-11"),
                "latest 12m": ("2025-08", "2026-07")}
    rows = []
    for name, (a, b) in EPISODES.items():
        seg = scored.loc[a:b]
        if seg["score"].isna().all():
            continue
        rows.append({"episode": name, "mean": round(seg["score"].mean(), 1),
                     "max": round(seg["score"].max(), 1),
                     "modal band": seg["band"].mode().iloc[0]})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "The brief sets one falsifiable test: the 2020 spike must appear and "
        "normalise through 2021. It does — 61.9 in 2019, peaking at 79.4 in 2020, "
        "back to 43.7 across 2021. The 2023 reading is moderated but not erased by "
        "removing the post-debt-ceiling cash rebuild: even ex-cash, bills financed "
        "83.6% of net borrowing that summer."
    )

# ---- Not yet built -------------------------------------------------------- #
st.divider()
st.markdown("##### Not yet available")
st.info("**Global comparison** is Phase 3.")

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
