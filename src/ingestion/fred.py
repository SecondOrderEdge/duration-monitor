"""FRED client.

The one credentialed source. The key is read from `FRED_API_KEY` and never
written anywhere: FRED puts it in the query string, so an unhandled request
error stringifies to a URL containing it, and this module is called from code
whose output gets committed. Errors are raised with the key scrubbed.

Series metadata — frequency, units, seasonal adjustment — is verified in
`config/sources.yaml` against a live probe rather than assumed, because two
inconsistencies in this feed produce plausible wrong numbers rather than errors:
`RRPONTSYD` is published in billions while `WALCL`, `WRESBAL` and `WTREGEN` are
in millions, and `GDP`, `FGRECPT` and `A091RC1Q027SBEA` are seasonally adjusted
annual rates while everything else is not. Both are recorded per series and
carried onto every row, so a downstream consumer cannot silently mix them.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import pandas as pd

from .fiscaldata import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    RETRY_STATUS,
    FiscalDataError,
    load_sources,
)

API_KEY_ENV = "FRED_API_KEY"
_API_KEY_RE = re.compile(r"(api_key=)[^&\s\"']+")

# FRED writes a missing observation as ".", not as an empty string or null.
FRED_MISSING = "."


class FredError(RuntimeError):
    """A FRED request failed, or the response cannot be trusted."""


class MissingCredential(FredError):
    """No API key available."""


def _redact(text: str, key: str | None) -> str:
    if key:
        text = text.replace(key, "***REDACTED***")
    return _API_KEY_RE.sub(r"\1***REDACTED***", text)


def api_key(explicit: str | None = None) -> str:
    key = explicit or os.environ.get(API_KEY_ENV)
    if not key:
        raise MissingCredential(
            f"{API_KEY_ENV} is not set. FRED is the only credentialed source; the "
            "key belongs in repository secrets for CI, or the shell for a local "
            "run. Cloud dev environments have no secrets store and should not "
            "carry it."
        )
    return key


@dataclass
class SeriesResult:
    series_id: str
    frame: pd.DataFrame
    retrieval_date: pd.Timestamp
    n_missing: int = 0


class FredClient:
    """Observation puller for the configured series.

    The HTTP session is injected so every path is testable without a network or a
    credential.
    """

    def __init__(
        self,
        sources: dict | None = None,
        *,
        key: str | None = None,
        session: Any = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        timeout: int = DEFAULT_TIMEOUT,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.sources = sources or load_sources()
        self.cfg = self.sources["fred"]
        self.base_url = self.cfg["base_url"].rstrip("/") + "/"
        self._key = api_key(key)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self._sleep = sleep

        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    # -- catalogue -------------------------------------------------------- #

    def configured_series(self) -> dict[str, str]:
        """series_id → group, from config."""
        return {
            sid: group
            for group, ids in self.cfg["series"].items()
            for sid in ids
        }

    def observed(self, series_id: str) -> dict:
        """Probe-verified metadata for a series.

        A series with no observed row was never confirmed against a live response,
        so its frequency and units are assumptions. Ingesting it would put an
        unverified unit into the store.
        """
        table = self.cfg.get("series_observed") or {}
        if series_id not in table:
            raise FredError(
                f"{series_id} has no verified metadata in config/sources.yaml. Run "
                "scripts/probe_sources.py --only fred and record it before ingesting."
            )
        return table[series_id]

    # -- HTTP ------------------------------------------------------------- #

    def _get(self, path: str, params: dict) -> dict:
        url = self.base_url + path
        last: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if attempt:
                self._sleep(self.backoff_base ** attempt)
            try:
                resp = self.session.get(
                    url, params={**params, "api_key": self._key, "file_type": "json"},
                    timeout=self.timeout,
                )
                status = getattr(resp, "status_code", 200)
                if status in RETRY_STATUS:
                    last = FredError(f"HTTP {status}")
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - re-raised scrubbed below
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status not in RETRY_STATUS:
                    raise FredError(
                        _redact(f"{url}: HTTP {status}: {exc}", self._key)
                    ) from None
                last = exc

        raise FredError(
            _redact(f"{url}: giving up after {self.max_retries} retries: {last}", self._key)
        ) from None

    # -- observations ----------------------------------------------------- #

    def fetch_series(self, series_id: str, *, start: str | None = None) -> SeriesResult:
        """Pull one series' full observation history."""
        meta = self.observed(series_id)

        params = {"series_id": series_id}
        if start:
            params["observation_start"] = start

        payload = self._get("series/observations", params)
        observations = payload.get("observations", [])

        frame = pd.DataFrame(observations)
        if frame.empty:
            raise FredError(f"{series_id}: no observations returned")

        # FRED writes a missing observation as "."; coercing without saying so
        # would turn a documented gap into an ordinary NaN.
        raw_values = frame["value"].astype(str)
        n_missing = int((raw_values.str.strip() == FRED_MISSING).sum())

        out = pd.DataFrame(
            {
                "date": pd.to_datetime(frame["date"]),
                "series_id": series_id,
                "value": pd.to_numeric(raw_values.replace(FRED_MISSING, pd.NA),
                                       errors="coerce"),
                "frequency": meta["freq"],
                "units": meta["units"],
                "seasonal_adjustment": meta.get("sa"),
                "source": "fred",
            }
        )

        unexpected = int(out["value"].isna().sum()) - n_missing
        if unexpected > 0:
            raise FredError(
                f"{series_id}: {unexpected} value(s) failed to coerce that were not "
                f"FRED's documented missing marker {FRED_MISSING!r}"
            )

        return SeriesResult(
            series_id=series_id,
            frame=out,
            retrieval_date=pd.Timestamp.now("UTC"),
            n_missing=n_missing,
        )

    def fetch_group(self, group: str, *, start: str | None = None) -> pd.DataFrame:
        """Pull every series in a configured group into one long table."""
        ids = self.cfg["series"].get(group)
        if ids is None:
            raise FredError(
                f"unknown series group {group!r}; configured: "
                f"{sorted(self.cfg['series'])}"
            )
        return self.fetch_many(ids, start=start)

    def fetch_many(self, series_ids: Iterable[str], *, start: str | None = None
                   ) -> pd.DataFrame:
        frames = []
        for sid in series_ids:
            result = self.fetch_series(sid, start=start)
            frame = result.frame
            frame["retrieval_date"] = result.retrieval_date
            frames.append(frame)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)
