"""Tests for the FRED and NY Fed ACM readers.

Both sources have a failure mode that produces a well-formed series rather than
an error, and each has a test here for exactly that: FRED writes missing values
as "." (coerced blindly, a documented gap becomes an ordinary NaN), and the ACM
workbook has two sheets whose wrong one is the pandas default (month-end term
premia are entirely plausible daily values).
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.ingestion.fred import FredClient, FredError, MissingCredential, _redact
from src.ingestion.nyfed import NyFedError, detect_revisions, parse_acm

# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {})})
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


SOURCES = {
    "fred": {
        "base_url": "https://example.invalid/fred/",
        "api_key_env": "FRED_API_KEY",
        "series": {"rates": ["DGS10"], "liquidity": ["RRPONTSYD"]},
        "series_observed": {
            "DGS10": {"freq": "D", "units": "percent", "sa": "NSA",
                      "start": "1962-01-02", "end": "2026-08-14"},
            "RRPONTSYD": {"freq": "D", "units": "billions_usd", "sa": "NSA",
                          "start": "2003-02-07", "end": "2026-08-18"},
        },
    }
}

KEY = "abcdef0123456789abcdef0123456789"


def observations(rows: list[tuple[str, str]]) -> FakeResponse:
    return FakeResponse({"observations": [{"date": d, "value": v} for d, v in rows]})


def client(responses: list) -> FredClient:
    return FredClient(SOURCES, key=KEY, session=FakeSession(responses),
                      sleep=lambda _: None)


# --------------------------------------------------------------------------- #
# FRED credentials
# --------------------------------------------------------------------------- #


def test_missing_credential_is_a_named_error(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(MissingCredential, match="FRED_API_KEY"):
        FredClient(SOURCES, session=FakeSession([]))


def test_key_is_scrubbed_from_errors():
    """FRED puts the key in the query string, so an error stringifies to it."""
    text = f"https://api.stlouisfed.org/fred/series?series_id=X&api_key={KEY}"
    out = _redact(text, KEY)
    assert KEY not in out
    assert "series_id=X" in out


def test_client_error_is_raised_scrubbed_not_retried():
    class HTTPError(Exception):
        def __init__(self):
            super().__init__(f"404 for url ...api_key={KEY}")
            self.response = FakeResponse({}, 404)

    c = client([HTTPError()])
    with pytest.raises(FredError) as excinfo:
        c.fetch_series("DGS10")
    assert KEY not in str(excinfo.value)


# --------------------------------------------------------------------------- #
# FRED observations
# --------------------------------------------------------------------------- #


def test_missing_marker_is_counted_not_silently_coerced():
    """FRED writes a gap as "."; coerced blindly it becomes an ordinary NaN."""
    c = client([observations([("2026-08-12", "4.25"), ("2026-08-13", "."),
                              ("2026-08-14", "4.31")])])
    result = c.fetch_series("DGS10")

    assert result.n_missing == 1
    assert result.frame["value"].isna().sum() == 1
    assert result.frame["value"].iloc[0] == pytest.approx(4.25)


def test_unexpected_uncoercible_value_raises():
    """A value that is neither a number nor FRED's documented gap marker."""
    c = client([observations([("2026-08-12", "4.25"), ("2026-08-13", "n/a")])])
    with pytest.raises(FredError, match="failed to coerce"):
        c.fetch_series("DGS10")


def test_observed_units_and_frequency_are_carried_onto_every_row():
    """Units differ by a factor of 1000 inside one group; rows must say which."""
    c = client([observations([("2026-08-18", "412.5")])])
    frame = c.fetch_series("RRPONTSYD").frame

    assert frame["units"].iloc[0] == "billions_usd"
    assert frame["frequency"].iloc[0] == "D"
    assert frame["seasonal_adjustment"].iloc[0] == "NSA"


def test_series_without_verified_metadata_refuses_to_ingest():
    c = client([])
    with pytest.raises(FredError, match="no verified metadata"):
        c.fetch_series("NOT_PROBED")


def test_empty_response_raises_rather_than_returning_an_empty_series():
    c = client([observations([])])
    with pytest.raises(FredError, match="no observations"):
        c.fetch_series("DGS10")


# --------------------------------------------------------------------------- #
# NY Fed ACM
# --------------------------------------------------------------------------- #

ACM_CFG = {
    "sheet": "ACM Daily",
    "engine": "xlrd",
    "series_of_interest": ["ACMTP02", "ACMTP05", "ACMTP10"],
}


def acm_sheet() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "DATE": ["05-Aug-2026", "06-Aug-2026", "07-Aug-2026"],
            "ACMTP02": [0.10, 0.12, 0.11],
            "ACMTP05": [0.40, 0.44, 0.43],
            "ACMTP10": [0.88, 0.90, 0.89],
            "ACMY10": [4.1, 4.2, 4.15],
        }
    )


def test_acm_parses_the_string_date_format():
    """DATE is `07-Aug-2026`, not an Excel serial; inference here is fragile."""
    out = parse_acm(acm_sheet(), ACM_CFG, retrieval_date=pd.Timestamp("2026-08-18"))
    assert out["date"].min() == pd.Timestamp("2026-08-05")
    assert out["date"].max() == pd.Timestamp("2026-08-07")


def test_acm_reshapes_to_the_long_term_premium_schema():
    out = parse_acm(acm_sheet(), ACM_CFG, retrieval_date=pd.Timestamp("2026-08-18"))
    assert set(out["maturity"]) == {"2Y", "5Y", "10Y"}
    assert (out["model"] == "ACM").all()
    assert len(out) == 9                       # 3 dates x 3 maturities
    ten = out[(out["maturity"] == "10Y") & (out["date"] == "2026-08-07")]
    assert ten["value"].iloc[0] == pytest.approx(0.89)


def test_acm_missing_contracted_series_raises():
    sheet = acm_sheet().drop(columns=["ACMTP05"])
    with pytest.raises(NyFedError, match="ACMTP05"):
        parse_acm(sheet, ACM_CFG, retrieval_date=pd.Timestamp("2026-08-18"))


def test_acm_unparseable_date_format_raises_rather_than_going_nat():
    sheet = acm_sheet()
    sheet.loc[1, "DATE"] = "2026/08/06"        # a layout change
    with pytest.raises(NyFedError, match="do not match the contracted format"):
        parse_acm(sheet, ACM_CFG, retrieval_date=pd.Timestamp("2026-08-18"))


def test_acm_layout_change_raises():
    sheet = acm_sheet().rename(columns={"DATE": "Date"})
    with pytest.raises(NyFedError, match="no DATE column"):
        parse_acm(sheet, ACM_CFG, retrieval_date=pd.Timestamp("2026-08-18"))


# --------------------------------------------------------------------------- #
# ACM revisions
# --------------------------------------------------------------------------- #


def test_revisions_in_history_are_detected():
    """ACM is re-estimated, so a 2010 value can change between two pulls."""
    previous = parse_acm(acm_sheet(), ACM_CFG, retrieval_date=pd.Timestamp("2026-08-11"))
    changed_sheet = acm_sheet()
    changed_sheet.loc[0, "ACMTP10"] = 0.95     # history restated
    current = parse_acm(changed_sheet, ACM_CFG, retrieval_date=pd.Timestamp("2026-08-18"))

    report = detect_revisions(previous, current)

    assert report.has_revisions
    assert len(report.changed) == 1
    assert report.changed["abs_change"].iloc[0] == pytest.approx(0.07)


def test_identical_vintages_report_no_revision():
    vintage = parse_acm(acm_sheet(), ACM_CFG, retrieval_date=pd.Timestamp("2026-08-11"))
    report = detect_revisions(vintage, vintage)

    assert not report.has_revisions
    assert report.n_compared == 9
