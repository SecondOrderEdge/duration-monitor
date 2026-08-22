"""Term premium and curve context."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from _shared import (
    ACCENT, MUTED, WARM, available, kpi, load, page, provenance, require, style,
)

from src import config
from src.calculations.curves import spread_context, spread_series
from src.calculations.issuance import bill_share
from src.calculations.percentiles import point_in_time_percentile

page("Term premium")
st.title("Term premium")
st.caption(
    "ACM is the primary source. Estimates are model output and are re-estimated "
    "retroactively, so every pull is diffed against the prior vintage rather than "
    "overwriting it."
)

if not require("term_premium"):
    st.stop()

tp = load("term_premium")
tp["maturity"] = tp["maturity"].astype(str)
wide = tp.pivot_table(index="date", columns="maturity", values="value").sort_index()

cols = st.columns(4)
for col, maturity in zip(cols, ["2Y", "5Y", "10Y"]):
    if maturity in wide.columns:
        series = wide[maturity].dropna()
        change = series.iloc[-1] - series.iloc[-253] if len(series) > 253 else float("nan")
        kpi(col, f"{maturity} term premium", f"{series.iloc[-1]:.2f}%",
            f"{change:+.2f}pp / 1y", note=f"as at {series.index[-1]:%Y-%m-%d}")

if "10Y" in wide.columns:
    monthly = wide["10Y"].resample("ME").last()
    pct_cfg = config.load("thresholds")["percentiles"]
    pit = point_in_time_percentile(
        pd.Series(monthly.values, index=monthly.index.to_period("M")),
        window=pct_cfg["window_months"],
        min_periods=pct_cfg["min_history_months"],
    )
    latest = pit.dropna()
    if len(latest):
        kpi(cols[3], "10y percentile", f"{latest.iloc[-1]:.0%}",
            note="point-in-time, trailing window")

st.divider()

st.markdown("##### ACM term premium")
fig = go.Figure()
fig.add_hline(y=0, line=dict(color=MUTED, width=1))
for maturity, colour in (("2Y", "#5b6478"), ("5Y", ACCENT), ("10Y", WARM)):
    if maturity in wide.columns:
        fig.add_trace(go.Scatter(x=wide.index, y=wide[maturity], name=maturity,
                                 line=dict(width=1.5, color=colour)))
st.plotly_chart(style(fig, ytitle="percent", height=420), use_container_width=True)
st.caption(
    "Daily series. The processed store keeps history from 1991 — a ten-year "
    "lead-in before the 2001 backtest start, which is the minimum history "
    "required before a point-in-time percentile may publish (Deviation D1). "
    "Earlier history back to 1961 stays in `data/raw`."
)

if "10Y" in wide.columns and available("debt_outstanding"):
    st.markdown("##### Against bill share")
    if True:
        share = bill_share(load("debt_outstanding"))
        monthly = wide["10Y"].resample("ME").last()
        monthly.index = monthly.index.to_period("M")
        aligned = pd.DataFrame({"bill_share": share, "term_premium": monthly}).dropna()

        horizon = config.load("thresholds")["alignment"]["interaction_flag_horizon_months"]
        both = (aligned["bill_share"].diff(horizon) > 0) & (
            aligned["term_premium"].diff(horizon) > 0
        )
        ax = aligned.index.to_timestamp()

        fig2 = go.Figure()
        for period in aligned.index[both]:
            fig2.add_vrect(x0=period.to_timestamp(), x1=(period + 1).to_timestamp(),
                           line_width=0, fillcolor=WARM, opacity=0.16, layer="below")
        fig2.add_trace(go.Scatter(x=ax, y=aligned["term_premium"], name="10y term premium",
                                  line=dict(color=WARM, width=2)))
        fig2.add_trace(go.Scatter(x=ax, y=aligned["bill_share"], name="Bill share",
                                  line=dict(color=ACCENT, width=1.5, dash="dot"),
                                  yaxis="y2"))
        fig2.update_layout(
            yaxis=dict(title="term premium, %"),
            yaxis2=dict(title="bill share", overlaying="y", side="right",
                        tickformat=".0%", showgrid=False,
                        tickfont=dict(color=MUTED)),
        )
        st.plotly_chart(style(fig2), use_container_width=True)
        st.caption(
            f"Shading marks months where both have risen over {horizon} months — "
            "the signature of the thesis, and the one reading that requires "
            "quantity and market-price evidence to agree. Daily term premium is "
            "resampled to month end; monthly data is never forward-filled onto a "
            "daily axis (Deviation D8)."
        )

st.info(
    "**Known limitation.** The backtest uses today's ACM vintage for history, "
    "because point-in-time ACM vintages are not freely available. Term premium "
    "history is therefore revised data used as if it were real-time. This cannot "
    "be fixed, only disclosed; `THREEFYTP10` (Kim-Wright) provides an independent "
    "model cross-check once FRED ingestion is running (Deviation D11)."
)



st.divider()
st.subheader("Curve spreads")
st.caption(
    "Context only, never a score input: a spread mixes rate expectations with "
    "term premium, so it frames the readings above rather than adding to them. "
    "Percentile is against ten trailing years, weak-ranked — the score's own "
    "convention."
)
if available("rates"):
    curves_cfg = config.load("thresholds")["curves"]
    spreads = spread_series(load("rates"), curves_cfg["spreads"])
    context = spread_context(spreads,
                             window_years=int(curves_cfg["percentile_window_years"]))
    ccols = st.columns(len(context))
    for col, row in zip(ccols, context.itertuples()):
        kpi(col, row.spread, f"{row.latest:+.2f}pp",
            f"{row.change_12m:+.2f} / 1y" if row.change_12m == row.change_12m else None,
            note=f"{row.percentile:.0f}th pctile · {row.as_of:%Y-%m-%d}")

    fig_sp = go.Figure()
    palette = {"2s10s": ACCENT, "5s30s": WARM, "10s30s": "#9aa3b5", "3m10y": "#5fa87a"}
    for name in spreads.columns:
        fig_sp.add_trace(go.Scatter(
            x=spreads.index, y=spreads[name], name=name, mode="lines",
            line=dict(color=palette.get(name, MUTED), width=1.4),
        ))
    fig_sp.add_hline(y=0, line=dict(color=MUTED, width=1, dash="dot"))
    st.plotly_chart(style(fig_sp, ytitle="percentage points"), width="stretch")
    st.caption(
        "Gaps are real: DGS20 is discontinued 1987-1993 and any spread on a "
        "missing leg stays missing rather than being bridged."
    )
else:
    st.info("Rates not built yet — run `python scripts/refresh.py --only rates`.")

provenance("term_premium")
