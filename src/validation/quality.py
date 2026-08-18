"""Data quality events.

A first-class table rather than log scraping, so the Data Quality page is a query
and CI can assert on it. Every event carries the same shape whatever produced it:
a failed fetch, a contract break, a stale feed, a parse failure, a detected
revision or a reconciliation break.

Staleness is the one that needs a stated convention rather than a number. A feed
is stale relative to its OWN publication cadence: the DTS publishes daily and is
stale after a few days, MSPD publishes monthly and is not late until well into
the following month. Comparing everything to one threshold would either cry wolf
on MSPD or stay silent on a dead daily feed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

EVENT_TYPES = (
    "fetch_failure", "contract_break", "staleness",
    "parse_failure", "revision", "reconciliation_break",
)
SEVERITIES = ("info", "warning", "error")

COLUMNS = [
    "event_date", "source", "endpoint", "event_type",
    "severity", "detail", "retrieval_date",
]


@dataclass
class QualityLog:
    """Accumulates events during a refresh."""

    events: list[dict] = field(default_factory=list)

    def record(
        self,
        *,
        source: str,
        endpoint: str,
        event_type: str,
        severity: str,
        detail: str,
        event_date: pd.Timestamp | None = None,
        retrieval_date: pd.Timestamp | None = None,
    ) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type {event_type!r}; expected {EVENT_TYPES}")
        if severity not in SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}; expected {SEVERITIES}")
        self.events.append(
            {
                "event_date": pd.Timestamp(event_date) if event_date is not None
                else pd.Timestamp.now("UTC").tz_localize(None),
                "source": source,
                "endpoint": endpoint,
                "event_type": event_type,
                "severity": severity,
                "detail": detail,
                "retrieval_date": pd.Timestamp(retrieval_date)
                if retrieval_date is not None else pd.NaT,
            }
        )

    @property
    def has_errors(self) -> bool:
        return any(e["severity"] == "error" for e in self.events)

    def to_frame(self) -> pd.DataFrame:
        if not self.events:
            return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})
        return pd.DataFrame(self.events)[COLUMNS]


def check_staleness(
    latest_observation: pd.Timestamp,
    *,
    source: str,
    endpoint: str,
    max_age_days: int,
    as_of: pd.Timestamp | None = None,
) -> dict | None:
    """Return a staleness event if the newest observation is older than allowed.

    Compared against the latest OBSERVATION date, not the retrieval date: a feed
    that is fetched successfully every morning and has not published anything for
    a month is stale, and a check on retrieval time would call it healthy.
    """
    as_of = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now("UTC").tz_localize(None)
    latest = pd.Timestamp(latest_observation)
    if pd.isna(latest):
        return {
            "source": source, "endpoint": endpoint, "event_type": "staleness",
            "severity": "error", "detail": "no observations at all",
        }

    age = (as_of - latest).days
    if age <= max_age_days:
        return None
    return {
        "source": source,
        "endpoint": endpoint,
        "event_type": "staleness",
        "severity": "error",
        "detail": (
            f"latest observation {latest:%Y-%m-%d} is {age} days old, "
            f"threshold {max_age_days}"
        ),
    }
