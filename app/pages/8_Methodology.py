"""Methodology, rendered from the committed docs so there is one source of truth."""

from __future__ import annotations

import streamlit as st

from _shared import DOCS, page

page("Methodology")
st.title("Methodology")

documents = {
    "Methodology": DOCS / "methodology.md",
    "Data dictionary": DOCS / "data_dictionary.md",
    "Implementation plan": DOCS / "implementation_plan.md",
}
available = {name: path for name, path in documents.items() if path.exists()}

if not available:
    st.warning("No methodology documents found under `docs/`.")
    st.stop()

choice = st.radio("Document", list(available), horizontal=True)
st.caption(f"Rendered from `docs/{available[choice].name}` — edit the file, not this page.")
st.divider()
st.markdown(available[choice].read_text(encoding="utf-8"))
