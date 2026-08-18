"""Data quality: staleness, failures, gaps, revisions and masked periods."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from _shared import BAD, GOOD, MUTED, PROCESSED, kpi, load, page, style, available

from src import config
from src.calculations.issuance import incremental_bill_funding, net_issuance
from src.validation.reconciliation import reconcile_components_to_total

page("Data quality")
st.title("Data quality")
st.caption(
    "Missing stays visibly missing. Nothing on this page is interpolated, and a "
    "figure that could not be reconciled is not published."
)

tables = ["debt_outstanding", "wam", "term_premium", "auctions", "rates",
          "long_end_stress", "data_quality_events"]

st.markdown("##### Processed tables")
rows = []
for name in tables:
    path = PROCESSED / f"{name}.parquet"
    if not path.exists():
        rows.append({"table": name, "state": "not built", "rows": None,
                     "latest observation": None, "size KB": None})
        continue
    df = load(name)
    date_col = next((c for c in ("observation_date", "date", "auction_date", "event_date")
                     if c in df.columns), None)
    latest = pd.to_datetime(df[date_col]).max() if date_col else None
    rows.append({
        "table": name,
        "state": "built",
        "rows": len(df),
        "latest observation": f"{latest:%Y-%m-%d}" if latest is not None and pd.notna(latest) else "—",
        "size KB": round(path.stat().st_size / 1024),
    })
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()
st.markdown("##### Events from the last refresh")
if available("data_quality_events"):
    events = load("data_quality_events")
    if len(events):
        errors = int((events["severity"] == "error").sum())
        st.error(f"{errors} error-level event(s) recorded.") if errors else st.warning(
            f"{len(events)} event(s) recorded."
        )
        st.dataframe(events, use_container_width=True, hide_index=True)
    else:
        st.success("No events recorded: every source refreshed, validated and current.")
else:
    st.info("No event table yet. Run `python scripts/refresh.py`.")

st.divider()
st.markdown("##### Reconciliation")
if available("debt_outstanding"):
    debt = load("debt_outstanding")
    tolerance = config.reconciliation_tolerance_pct()
    result = reconcile_components_to_total(debt, tolerance_pct=tolerance)

    c1, c2, c3 = st.columns(3)
    kpi(c1, "Periods checked", f"{result.n_periods}")
    kpi(c2, "Worst difference", f"{result.max_abs_diff_pct:.2e}%",
        note=f"tolerance {tolerance}%")
    kpi(c3, "Breaches", f"{len(result.breaches)}",
        note="summed classes vs published total")
    if result.ok:
        st.success(
            "Component classes sum to the published Total Marketable row within "
            "tolerance in every month. The residual is Treasury's own rounding."
        )
    else:
        st.error("Reconciliation breaks:")
        st.dataframe(result.breaches, use_container_width=True, hide_index=True)

st.divider()
st.markdown("##### Deliberately withheld figures")
if available("debt_outstanding"):
    net = net_issuance(load("debt_outstanding"))
    funding = incremental_bill_funding(net, min_abs_denominator=config.min_abs_denominator("M"))
    masked = funding["denominator_masked"]
    st.write(
        f"**{int(masked.sum())} of {len(masked)} months** have a masked incremental "
        "bill funding ratio."
    )
    st.caption(
        "Not a gap in the data. During a binding debt ceiling Treasury runs bills "
        "down and net borrowing approaches zero, so the ratio becomes unbounded "
        "and meaningless. The magnitude floor is a deliberate refusal to publish a "
        "number that would dominate every chart it appeared on (Deviation D5)."
    )
    with st.expander("Masked periods"):
        st.write(", ".join(str(p) for p in funding.index[masked]))

if available("auctions"):
    auctions = load("auctions")
    st.write(
        f"**{len(auctions):,} auctions** in the processed store, from "
        f"{auctions.auction_date.min():%Y-%m}."
    )
    st.caption(
        "Earlier auctions back to 1979 are ingested and archived in `data/raw` but "
        "not published here, because before about 2000 Treasury did not report "
        "bid-to-cover at all. They are kept rather than dropped — discarding them "
        "at ingestion would silently truncate the auction history while leaving a "
        "clean-looking series behind — and the count held back is recorded as an "
        "event above rather than left invisible."
    )

if available("term_premium"):
    tp = load("term_premium")
    if "revision_flag" in tp.columns:
        revised = int(tp["revision_flag"].sum())
        st.write(f"**{revised:,} term premium observations** changed since the prior vintage.")
        st.caption(
            "ACM is model output and is re-estimated retroactively. Revisions are "
            "flagged rather than silently overwritten, because a backtest run "
            "against a quietly restated history is not reproducible."
        )
