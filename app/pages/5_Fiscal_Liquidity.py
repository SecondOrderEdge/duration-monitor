"""Fiscal and liquidity context. Context, not signal."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from _shared import ACCENT, MUTED, WARM, kpi, load, page, provenance, require, style

page("Fiscal & liquidity")
st.title("Fiscal & liquidity")
st.caption(
    "Context for the issuance picture, not evidence for the thesis. Level of debt "
    "is context; direction of travel is the signal."
)

if not require("rates"):
    st.info(
        "This page reads the FRED tables. FRED is the one credentialed source and "
        "the key lives in repository secrets, so the series are built by the "
        "**Refresh data** workflow rather than locally. Run it, or set "
        "`FRED_API_KEY` and run `python scripts/refresh.py --only rates`."
    )
    st.stop()

rates = load("rates")
rates["series_id"] = rates["series_id"].astype(str)

# Units are NOT consistent across this feed and the inconsistency sits inside one
# group: RRPONTSYD is billions while WALCL, WRESBAL and WTREGEN are millions.
# Every row carries its observed units so a chart cannot silently mix them.
units = rates.groupby("series_id")["units"].first().to_dict()

wide = rates.pivot_table(index="date", columns="series_id", values="value").sort_index()

st.markdown("##### Yield curve")
curve_ids = [c for c in ["DGS3MO", "DGS2", "DGS10", "DGS30"] if c in wide.columns]
if curve_ids:
    fig = go.Figure()
    for sid in curve_ids:
        fig.add_trace(go.Scatter(x=wide.index, y=wide[sid], name=sid,
                                 line=dict(width=1.4)))
    st.plotly_chart(style(fig, ytitle="percent"), use_container_width=True)

    st.markdown("##### Curve spreads")
    spreads = {}
    if {"DGS2", "DGS10"} <= set(wide.columns):
        spreads["2s10s"] = wide["DGS10"] - wide["DGS2"]
    if {"DGS5", "DGS30"} <= set(wide.columns):
        spreads["5s30s"] = wide["DGS30"] - wide["DGS5"]
    if {"DGS10", "DGS30"} <= set(wide.columns):
        spreads["10s30s"] = wide["DGS30"] - wide["DGS10"]
    if {"DGS3MO", "DGS10"} <= set(wide.columns):
        spreads["3m10y"] = wide["DGS10"] - wide["DGS3MO"]

    if spreads:
        cols = st.columns(len(spreads))
        for col, (name, series) in zip(cols, spreads.items()):
            clean = series.dropna()
            pct = (clean <= clean.iloc[-1]).mean()
            kpi(col, name, f"{clean.iloc[-1]*100:+.0f}bp",
                note=f"{pct:.0%} of full-sample history below")

        fig2 = go.Figure()
        fig2.add_hline(y=0, line=dict(color=MUTED, width=1))
        for name, series in spreads.items():
            fig2.add_trace(go.Scatter(x=series.index, y=series * 100, name=name,
                                      line=dict(width=1.2)))
        st.plotly_chart(style(fig2, ytitle="basis points"), use_container_width=True)
        st.caption(
            "Percentiles here are FULL-SAMPLE and descriptive only — they rank "
            "today against data that includes today. They are context on a chart, "
            "never an input to the score, which uses point-in-time ranks "
            "(Deviation D1)."
        )

st.markdown("##### Liquidity")
liq_ids = [c for c in ["WALCL", "WRESBAL", "WTREGEN", "RRPONTSYD"] if c in wide.columns]
if liq_ids:
    fig3 = go.Figure()
    for sid in liq_ids:
        # Normalise to $tn from each series' own published units.
        divisor = 1e6 if units.get(sid) == "millions_usd" else 1e3
        fig3.add_trace(go.Scatter(x=wide.index, y=wide[sid] / divisor, name=sid,
                                  line=dict(width=1.4)))
    st.plotly_chart(style(fig3, ytitle="$tn"), use_container_width=True)
    st.caption(
        "Series are converted to trillions from their OWN published units. "
        "RRPONTSYD is published in billions while WALCL, WRESBAL and WTREGEN are "
        "in millions — netting them without scaling is a 1000x error that still "
        "plots as a plausible line."
    )

with st.expander("Series units and seasonal adjustment"):
    meta = (
        rates.groupby("series_id")[["frequency", "units", "seasonal_adjustment"]]
        .first().reset_index()
    )
    st.dataframe(meta, use_container_width=True, hide_index=True)
    st.caption(
        "GDP, FGRECPT and A091RC1Q027SBEA are SAAR — already annualised — while "
        "everything else is NSA. Summing four quarters of a SAAR series overstates "
        "by roughly 4x."
    )

provenance("rates")
