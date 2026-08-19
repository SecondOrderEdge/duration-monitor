"""Euro-area sovereigns, scored on the quantity-only variant.

Two things this page exists to prevent, both of which the number alone invites:

**Reading these against the US score.** They are different measurements. A
quantity-only 63 was reached without any market-price evidence; a full 63
required it. The variant is carried on every row and `comparable()` decides what
may share an axis — the check is executed here, not left to a comment.

**Reading the score as an absolute claim.** Every factor here is a
point-in-time percentile rank, so the composite measures a country against its
own recent behaviour and never against zero. France's bill share has fallen in
70% of the last 40 quarters; a smaller-than-usual fall ranks high while the stock
is still going DOWN. The absolute direction is therefore shown next to every
score, not buried in a footnote.

No interpretation band is shown. The band cut-points were backtested on the
six-factor US score, and this composite measurably runs wider — so the same
numbers would not mean the same thing. See `bands_for_variant`.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from _shared import (ACCENT, BAD, GOOD, GRID, MUTED, WARM, kpi, load, page,
                     provenance, require, staleness_banner, style)

from src import config
from src.signals.duration_shift_score import band_contradicts_direction, comparable

page("Cross-country")
st.title("Cross-country")
st.caption(
    "Germany, France and Italy on the QUANTITY-ONLY variant: three of six "
    "factors, quarterly. Not comparable to the US score."
)

if not require("euro_score", "euro_debt"):
    st.stop()

# Quarterly data published a quarter in arrears is ALREADY ~100 days old when
# it appears, so it is judged against its own cadence rather than the daily
# sources' — otherwise a healthy euro feed would show as permanently stale.
staleness_banner({"euro_debt": "eurostat_quarterly"})

scores = load("euro_score")
scores["period_end"] = pd.PeriodIndex(scores["period"], freq="Q").to_timestamp(how="end")
weights_cfg = config.load("factor_weights")

variants = sorted(scores["variant"].dropna().unique())
if len(variants) != 1:
    st.error(
        f"This page plots one axis and the data carries variants {variants}. "
        "Scores from different variants are different measurements and must not "
        "share a chart."
    )
    st.stop()
variant = variants[0]

st.info(
    f"**Variant `{variant}`** — "
    + weights_cfg["score_variants"][variant]["description"].strip()
    + f"\n\nFactors: {', '.join(weights_cfg['score_variants'][variant]['factors'])}. "
    "No WAM, no term premium, no auction stress: no free source publishes them "
    "for these sovereigns (`docs/phase3_source_assessment.md`). **No regime is "
    "assigned** — the regime classifier caps a high score using market-price "
    "corroboration, and there is none here."
)

# The US number is deliberately absent from every chart below. Stated as an
# executed check rather than a promise, so that configuring the two variants as
# comparable would change the page instead of quietly invalidating its caption.
if not comparable(variant, "full", weights_cfg):
    st.warning(
        f"The US score is **not shown on this page**. `{variant}` and `full` are "
        "declared incomparable in `config/factor_weights.yaml`, so putting them "
        "on one axis would read as a ranking and would not be one."
    )

latest = (
    scores.dropna(subset=["score"])
    .sort_values("period_end")
    .groupby("country", observed=True)
    .tail(1)
    .set_index("country")
)

st.subheader("Latest reading")
cols = st.columns(len(latest))
for col, (country, row) in zip(cols, latest.iterrows()):
    # The band and the absolute direction are shown TOGETHER because they can
    # disagree, and the disagreement is the point: a relative score presented
    # without its absolute direction is the failure mode this variant creates.
    direction = row.get("direction_absolute")
    change = row.get("bill_share_4q_change")
    arrow = {"shortening": "↑ shortening", "extending": "↓ extending"}.get(
        direction, "→ flat"
    )
    band = row.get("band")
    note = f"{band} · {row['period']}" if isinstance(band, str) else str(row["period"])
    kpi(col, f"{country}", f"{row['score']:.1f}", note=note)
    with col:
        colour = BAD if direction == "shortening" else GOOD if direction == "extending" else MUTED
        st.markdown(
            f"<div style='color:{colour};font-size:0.9rem'>Bill share {arrow}"
            + (f" ({change:+.2%} over 4q)" if pd.notna(change) else "")
            + "</div>",
            unsafe_allow_html=True,
        )

# Only meaningful where a band is published at all. It is kept rather than
# deleted because withdrawing the band is a decision that can be revisited, and
# the contradiction it guards against would come straight back with it.
disagree = latest[[
    band_contradicts_direction(b, d)
    for b, d in zip(latest.get("band", pd.Series(dtype=object)),
                    latest["direction_absolute"])
]] if "band" in latest.columns else latest.iloc[:0]
if len(disagree):
    st.warning(
        "**The band name and the absolute direction disagree for "
        + ", ".join(map(str, disagree.index))
        + ".** The score is a percentile rank against each country's own history, "
        "so it reads high when a country extends more slowly than usual — and the "
        "band is then named for a direction the bill share is not moving in. Read "
        "the direction for what is happening, and the score for how it compares "
        "to that sovereign's own recent behaviour."
    )

st.divider()

st.subheader("Score history")
fig = go.Figure()
palette = {"DE": ACCENT, "FR": WARM, "IT": "#9aa3b5"}
for country, group in scores.dropna(subset=["score"]).groupby("country", observed=True):
    group = group.sort_values("period_end")
    fig.add_trace(go.Scatter(
        x=group["period_end"], y=group["score"], name=str(country),
        mode="lines", line=dict(color=palette.get(str(country), MUTED), width=1.8),
    ))
fig.add_hline(y=50, line=dict(color=GRID, width=1, dash="dot"))
st.plotly_chart(style(fig, ytitle=f"score ({variant})"), width="stretch")
st.caption(
    "The 50 line is the midpoint of each country's own history, not a threshold. "
    "No band shading: the US band cut-points are not validated for this variant, "
    "which runs wider (sd 23.4 against 19.2), so they would reach further into "
    "the tail here than the backtest ever tested."
)
st.caption(
    "Gaps are quarters with no score, not zero readings. `min_factors` is 3 of 3, "
    "so a quarter whose funding ratio is masked by the small-denominator floor "
    "has no score at all rather than a two-factor one — a two-factor reading "
    "would be a third measurement sharing a name with this one."
)

st.subheader("Bill share, absolute")
bill = go.Figure()
debt = load("euro_debt")
wide = debt.pivot_table(
    index=["observation_date", "country"], columns="security_class",
    values="amount_outstanding", aggfunc="first",
).reset_index()
wide["bill_share"] = wide["BILLS"] / wide["TOTAL_MARKETABLE"]
for country, group in wide.groupby("country", observed=True):
    group = group.sort_values("observation_date")
    bill.add_trace(go.Scatter(
        x=group["observation_date"], y=group["bill_share"], name=str(country),
        mode="lines", line=dict(color=palette.get(str(country), MUTED), width=1.8),
    ))
st.plotly_chart(style(bill, ytitle="bills / total"), width="stretch")
st.caption(
    "The level the score never sees. Eurostat publishes no total, so "
    "TOTAL_MARKETABLE here is the SUM of short- and long-term securities — "
    "flagged `total_is_derived`, and the reconciliation check that guards the US "
    "series has nothing to test against."
)

provenance("euro_score", observation=str(latest["period"].max()))
