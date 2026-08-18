"""NY Fed ACM term premium.

No API — a scheduled pull of a legacy .xls workbook. Three properties of that
file are load-bearing and all three are recorded in `config/sources.yaml` from a
live probe rather than assumed:

**The workbook has two sheets and the pandas default is the wrong one.** Reading
without an explicit `sheet_name` returns "ACM Monthly" — 782 month-end rows —
which then gets used as the daily series it is not. Nothing fails: month-end term
premia are entirely plausible daily values, and the resampling Deviation D8 calls
for would be quietly skipped rather than performed.

**It is a genuine legacy .xls.** openpyxl cannot read it; the engine is xlrd and
is pinned, not discovered by fallback.

**DATE is a string, not an Excel serial.** It arrives formatted `07-Aug-2026`,
so it is parsed with an explicit format — inference on this layout is
locale-sensitive and fails to NaT or, worse, a plausible wrong year.

ACM estimates are model output and are re-estimated retroactively, so every pull
carries its retrieval date and is diffed against the previous vintage rather than
overwriting it.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

from .fiscaldata import DEFAULT_TIMEOUT, load_sources

ACM_DATE_FORMAT = "%d-%b-%Y"


class NyFedError(RuntimeError):
    """The workbook could not be retrieved, or is not the file we contracted for."""


@dataclass
class RevisionReport:
    """Historical values that changed between two vintages."""

    n_compared: int = 0
    changed: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def has_revisions(self) -> bool:
        return not self.changed.empty


def fetch_acm(
    sources: dict | None = None,
    *,
    session=None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Download and parse the ACM workbook. Returns (long table, retrieval date)."""
    cfg = (sources or load_sources())["nyfed_acm"]

    if session is None:
        import requests

        session = requests.Session()

    resp = session.get(cfg["url"], timeout=timeout)
    resp.raise_for_status()
    content = resp.content
    retrieval_date = pd.Timestamp.now("UTC")

    sheet = cfg.get("sheet")
    if not sheet:
        raise NyFedError(
            "config/sources.yaml does not name a sheet for the ACM workbook. The "
            "file has two, and the pandas default is the monthly one — reading it "
            "as daily is silent and wrong."
        )

    try:
        raw = pd.read_excel(
            io.BytesIO(content), sheet_name=sheet, engine=cfg.get("engine", "xlrd")
        )
    except Exception as exc:  # noqa: BLE001
        raise NyFedError(
            f"could not parse the ACM workbook sheet {sheet!r} with engine "
            f"{cfg.get('engine')!r}: {type(exc).__name__}: {exc}"
        ) from exc

    return parse_acm(raw, cfg, retrieval_date=retrieval_date), retrieval_date


def parse_acm(
    raw: pd.DataFrame, cfg: dict, *, retrieval_date: pd.Timestamp
) -> pd.DataFrame:
    """Reshape the workbook to the `term_premium` long schema."""
    if "DATE" not in raw.columns:
        raise NyFedError(
            f"ACM sheet has no DATE column; got {list(raw.columns)[:8]}. The "
            "workbook layout has changed."
        )

    wanted = list(cfg.get("series_of_interest") or [])
    missing = [s for s in wanted if s not in raw.columns]
    if missing:
        raise NyFedError(
            f"ACM sheet is missing contracted series {missing}; present columns "
            f"include {[c for c in raw.columns if str(c).startswith('ACMTP')]}"
        )

    dates = _parse_dates(raw["DATE"])

    frames = []
    for column in wanted:
        maturity = f"{int(column.replace('ACMTP', ''))}Y"
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "country": "US",
                    "maturity": maturity,
                    "model": "ACM",
                    "value": pd.to_numeric(raw[column], errors="coerce"),
                }
            )
        )

    out = pd.concat(frames, ignore_index=True)
    out["units"] = "percent"
    out["source"] = "nyfed_acm"
    out["vintage_date"] = retrieval_date
    out["retrieval_date"] = retrieval_date
    out["revision_flag"] = False
    return out.dropna(subset=["date"]).sort_values(["date", "maturity"]).reset_index(drop=True)


def _parse_dates(column: pd.Series) -> pd.Series:
    """Parse the DATE column, which is a string in `%d-%b-%Y`.

    Falls back to generic parsing only if the explicit format matches nothing —
    a layout change should surface as a parse error, not as silent NaT.
    """
    if pd.api.types.is_datetime64_any_dtype(column):
        return pd.to_datetime(column)

    parsed = pd.to_datetime(column, format=ACM_DATE_FORMAT, errors="coerce")
    if parsed.notna().any():
        failures = int(parsed.isna().sum())
        if failures:
            raise NyFedError(
                f"{failures} ACM date(s) do not match the contracted format "
                f"{ACM_DATE_FORMAT!r}; the workbook layout has changed"
            )
        return parsed

    generic = pd.to_datetime(column, errors="coerce")
    if generic.isna().all():
        raise NyFedError(
            f"no ACM date parsed with {ACM_DATE_FORMAT!r} or by inference; "
            f"first values were {list(column.head(3))}"
        )
    return generic


def detect_revisions(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    *,
    tolerance: float = 1e-9,
) -> RevisionReport:
    """Compare two ACM vintages on their overlapping history.

    ACM is re-estimated, so a value dated 2010 can differ between two pulls. That
    is normal and must be visible: overwriting silently would make a backtest
    irreproducible with no trace of why.
    """
    keys = ["date", "maturity", "model"]
    merged = previous.merge(
        current, on=keys, suffixes=("_prev", "_curr"), how="inner"
    )
    if merged.empty:
        return RevisionReport(n_compared=0)

    delta = (merged["value_curr"] - merged["value_prev"]).abs()
    changed = merged.loc[delta > tolerance, [*keys, "value_prev", "value_curr"]].copy()
    changed["abs_change"] = delta[delta > tolerance].values

    return RevisionReport(n_compared=len(merged), changed=changed)
