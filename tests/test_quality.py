"""Tests for the data quality event log and staleness checks."""

from __future__ import annotations

import pandas as pd
import pytest

from src.validation.quality import COLUMNS, QualityLog, check_staleness


def test_events_render_with_the_declared_schema():
    log = QualityLog()
    log.record(source="fred", endpoint="DGS10", event_type="fetch_failure",
               severity="error", detail="timeout")
    frame = log.to_frame()

    assert list(frame.columns) == COLUMNS
    assert len(frame) == 1
    assert log.has_errors


def test_empty_log_still_has_the_schema():
    """The Data Quality page queries this table; an empty one must still be a table."""
    assert list(QualityLog().to_frame().columns) == COLUMNS
    assert not QualityLog().has_errors


def test_unknown_event_type_or_severity_is_rejected():
    log = QualityLog()
    with pytest.raises(ValueError, match="unknown event_type"):
        log.record(source="x", endpoint="y", event_type="vibes",
                   severity="error", detail="")
    with pytest.raises(ValueError, match="unknown severity"):
        log.record(source="x", endpoint="y", event_type="staleness",
                   severity="catastrophic", detail="")


def test_info_events_do_not_make_the_log_fail():
    log = QualityLog()
    log.record(source="auctions", endpoint="auctions_query", event_type="staleness",
               severity="info", detail="pre-2008 auctions held back")
    assert not log.has_errors


# --------------------------------------------------------------------------- #
# staleness
# --------------------------------------------------------------------------- #


def test_fresh_feed_produces_no_event():
    event = check_staleness(pd.Timestamp("2026-08-15"), source="mspd",
                            endpoint="mspd_table_1", max_age_days=45,
                            as_of=pd.Timestamp("2026-08-18"))
    assert event is None


def test_stale_feed_is_flagged_against_its_own_cadence():
    """A monthly feed is not late until well into the following month.

    One threshold for every source would either cry wolf on MSPD or stay silent
    on a dead daily feed.
    """
    monthly_ok = check_staleness(pd.Timestamp("2026-07-31"), source="mspd",
                                 endpoint="mspd_table_1", max_age_days=45,
                                 as_of=pd.Timestamp("2026-08-18"))
    daily_stale = check_staleness(pd.Timestamp("2026-07-31"), source="fred",
                                  endpoint="DGS10", max_age_days=5,
                                  as_of=pd.Timestamp("2026-08-18"))
    assert monthly_ok is None
    assert daily_stale is not None
    assert daily_stale["severity"] == "error"
    assert "18 days old" in daily_stale["detail"]


def test_staleness_is_measured_on_the_observation_not_the_retrieval():
    """A feed fetched every morning that has published nothing for a month is stale."""
    event = check_staleness(pd.Timestamp("2026-06-01"), source="nyfed_acm",
                            endpoint="acm", max_age_days=10,
                            as_of=pd.Timestamp("2026-08-18"))
    assert event is not None
    assert event["event_type"] == "staleness"


def test_a_feed_with_no_observations_at_all_is_an_error():
    event = check_staleness(pd.NaT, source="fred", endpoint="DGS10",
                            max_age_days=5, as_of=pd.Timestamp("2026-08-18"))
    assert event is not None
    assert "no observations" in event["detail"]


# --------------------------------------------------------------------------- #
# the banner the deployed app shows
# --------------------------------------------------------------------------- #


def test_the_app_and_the_pipeline_use_one_staleness_rule():
    """The banner must not reimplement the comparison the pipeline already owns.

    Two copies of a staleness rule drift, and the one on the page is the one a
    reader would trust. This pins that `stale_tables` delegates rather than
    duplicating: the app module imports the pipeline's checker.
    """
    import pathlib

    shared = (pathlib.Path(__file__).resolve().parents[1] / "app" / "_shared.py").read_text()
    assert "from src.validation.quality import check_staleness" in shared
    assert "stale_tables" in shared


def test_staleness_thresholds_cover_every_source_the_banner_watches():
    """A table watched with no configured cadence would be silently skipped."""
    import yaml
    from src.config import CONFIG_DIR

    configured = yaml.safe_load((CONFIG_DIR / "thresholds.yaml").read_text())[
        "validation"
    ]["staleness_days"]
    watched = {"mspd", "nyfed_acm", "auctions", "fred_daily"}
    assert watched <= set(configured), sorted(watched - set(configured))
