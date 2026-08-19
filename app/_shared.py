"""Shared loading, styling and formatting for every page.

Kept in one place so the pages cannot drift apart on palette or, more
importantly, on how they read data: every page reads `data/processed/` and
nothing else, cached on file mtime, and no page calls an API at load.
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PROCESSED = REPO_ROOT / "data" / "processed"
DOCS = REPO_ROOT / "docs"

# Restrained institutional palette. Bills — the subject of the thesis — carry the
# only saturated colour; everything else recedes.
INK = "#e6e9ef"
MUTED = "#8b93a7"
GRID = "#1e2330"
PAPER = "#0e1117"
ACCENT = "#4c9be8"
WARM = "#d98a4a"
GOOD = "#5fa87a"
BAD = "#c96a6a"

SERIES = {
    "BILLS": ACCENT, "NOTES": "#5b6478", "BONDS": "#7d8799",
    "TIPS": "#9aa3b5", "FRN": "#4a5262", "OTHER": "#3a4150",
}


def page(title: str, *, icon: str = "📉") -> None:
    st.set_page_config(page_title=f"{title} · Duration Monitor", page_icon=icon,
                       layout="wide", initial_sidebar_state="expanded")


def available(name: str) -> bool:
    return (PROCESSED / f"{name}.parquet").exists()


def _mtime(name: str) -> float:
    return (PROCESSED / f"{name}.parquet").stat().st_mtime


@st.cache_data(show_spinner=False)
def _read(name: str, _mtime_key: float) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / f"{name}.parquet")


def load(name: str) -> pd.DataFrame:
    """Read a processed table, re-reading only when the pipeline has rewritten it."""
    return _read(name, _mtime(name))


def require(*names: str) -> bool:
    """Render an explanation and return False when a table has not been built.

    A page that renders empty is indistinguishable from one whose data is
    genuinely flat, so a missing table says so and says how to fix it.
    """
    missing = [n for n in names if not available(n)]
    if not missing:
        return True
    st.warning(
        f"Not built yet: {', '.join(f'`{m}`' for m in missing)}. Run "
        f"`python scripts/refresh.py --only {missing[0]}` to build it."
    )
    return False


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


def kpi(col, label: str, value: str, delta: str | None = None,
        note: str | None = None, unavailable: bool = False) -> None:
    """One KPI card. `unavailable` renders an em dash and why, never a zero."""
    with col:
        if unavailable:
            st.metric(label, "—")
            st.caption(note or "not yet ingested")
        else:
            st.metric(label, value, delta)
            if note:
                st.caption(note)


def stale_tables(tables: dict[str, str] | None = None) -> list[dict]:
    """Processed tables whose newest observation is older than their own cadence.

    Uses the same `check_staleness` the refresh pipeline uses, rather than
    reimplementing the comparison — two copies of a staleness rule drift, and the
    one on the page is the one a reader would trust.
    """
    from src import config
    from src.validation.quality import check_staleness

    thresholds = config.load("thresholds")["validation"]["staleness_days"]
    tables = tables or {"debt_outstanding": "mspd", "term_premium": "nyfed_acm",
                        "auctions": "auctions", "rates": "fred_daily"}

    events = []
    for table, key in tables.items():
        if not available(table) or key not in thresholds:
            continue
        frame = load(table)
        column = next((c for c in ("observation_date", "date", "auction_date")
                       if c in frame.columns), None)
        if column is None:
            continue
        event = check_staleness(
            pd.to_datetime(frame[column]).max(),
            source=table, endpoint=table, max_age_days=thresholds[key],
        )
        if event:
            events.append(event)
    return events


def staleness_banner(tables: dict[str, str] | None = None) -> None:
    """Warn on the page when the data behind it has stopped being refreshed.

    The deployed app reads whatever the last committed refresh produced, so a
    broken workflow does not break the app — it makes it quietly serve old
    figures under a current-looking chart. The Data Quality page records
    staleness events, but only when a refresh actually ran; a workflow that
    stopped firing records nothing at all. This checks the age of the data
    itself, where the reader is actually looking.
    """
    events = stale_tables(tables)
    if not events:
        return
    lines = "\n- ".join(f"**{e['source']}** — {e['detail']}" for e in events)
    st.warning(
        "Some series have not been refreshed within their expected cadence, so the "
        f"readings below may be out of date:\n\n- {lines}\n\nCadences differ by "
        "source — MSPD publishes monthly, the DTS daily — so each is judged "
        "against its own."
    )


def provenance(table: str, *, observation: str | None = None) -> None:
    """Sidebar provenance block. Every page states what it is showing and when."""
    df = load(table)
    with st.sidebar:
        st.markdown("### Provenance")
        if observation:
            st.write(f"**Observation** {observation}")
        if "retrieval_date" in df.columns:
            retrieved = pd.to_datetime(df["retrieval_date"]).max()
            if pd.notna(retrieved):
                st.write(f"**Retrieved** {retrieved:%Y-%m-%d %H:%M} UTC")
        if "source" in df.columns:
            sources = sorted({str(s) for s in df["source"].dropna().unique()})
            st.caption("Source: " + ", ".join(f"`{s}`" for s in sources))
