"""Treasury Fiscal Data API client.

Ingestion's job is to retrieve and store, exactly as retrieved. No cleaning, no
arithmetic, no type inference — those belong to the transformation layer. What
this module *does* own is refusing to proceed when the source has changed
underneath the contract, because a field that silently disappears becomes a
column of NaN that looks like missing data rather than a broken mapping.

Three failure modes this guards against, all of which produce plausible-looking
output rather than an error if left alone:

**A contracted field disappears.** `config/sources.yaml` declares the fields
ingestion depends on. If the API stops returning one, `fetch` raises rather than
handing back a frame whose column is quietly absent.

**Pagination silently truncates.** The API paginates with `page[number]` /
`page[size]` and reports `total-count`. A dropped page yields a shorter frame
that is still perfectly well-formed — a bill share computed from 9 of 10 pages is
simply wrong, with nothing to indicate it. Every fetch reconciles rows retrieved
against the count the API declared, and raises on a shortfall.

**The data shifts mid-pagination.** A refresh landing between page 3 and page 4
changes the offsets under us, so rows get duplicated or skipped. `total-count` is
re-checked on every page and a change aborts the fetch.

Retries cover network faults, 429 and 5xx. A 4xx is a bug in the request and is
raised immediately rather than retried four times.
"""

from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

import pandas as pd
import yaml

from .typed import ParseReport, add_provenance, parse_typed

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "sources.yaml"

RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
DEFAULT_PAGE_SIZE = 10000
DEFAULT_MAX_RETRIES = 4
DEFAULT_BACKOFF_BASE = 2.0
DEFAULT_TIMEOUT = 45


class FiscalDataError(RuntimeError):
    """Base class for every failure this module raises deliberately."""


class ContractBreak(FiscalDataError):
    """The live response no longer matches config/sources.yaml."""


class PaginationError(FiscalDataError):
    """The set of rows retrieved cannot be trusted to be complete."""


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #

def load_sources(path: pathlib.Path | str = DEFAULT_CONFIG) -> dict:
    """Load the source registry."""
    return yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))


def endpoint_spec(name: str, sources: dict | None = None) -> dict:
    """Look up one fiscaldata endpoint, refusing unverified ones.

    `verified: false` means no live response has confirmed the field names, so
    any mapping built on them is a guess. Ingestion will not run against a guess.
    """
    sources = sources or load_sources()
    fd = sources["fiscaldata"]
    try:
        spec = fd["endpoints"][name]
    except KeyError:
        raise KeyError(
            f"unknown fiscaldata endpoint {name!r}; "
            f"known: {sorted(fd['endpoints'])}"
        ) from None
    if not spec.get("verified", False):
        raise ContractBreak(
            f"{name}: config/sources.yaml marks this endpoint unverified. Run "
            "scripts/probe_sources.py and correct the contract before ingesting it."
        )
    return spec


# --------------------------------------------------------------------------- #
# results
# --------------------------------------------------------------------------- #

@dataclass
class FetchResult:
    """A retrieval, with everything needed to audit it later."""

    endpoint: str
    frame: pd.DataFrame               # raw strings, exactly as returned
    url: str
    params: dict
    retrieval_date: pd.Timestamp
    total_count: int | None = None    # as declared by the API
    n_pages: int = 0
    n_retries: int = 0
    observed_fields: list[str] = field(default_factory=list)
    added_fields: list[str] = field(default_factory=list)
    dropped_fields: list[str] = field(default_factory=list)

    @property
    def n_rows(self) -> int:
        return len(self.frame)

    def manifest(self) -> dict:
        """Sidecar record written next to the parquet."""
        return {
            "endpoint": self.endpoint,
            "url": self.url,
            "params": {k: str(v) for k, v in self.params.items()},
            "retrieval_date": self.retrieval_date.isoformat(),
            "n_rows": self.n_rows,
            "total_count_declared": self.total_count,
            "n_pages": self.n_pages,
            "n_retries": self.n_retries,
            "observed_fields": self.observed_fields,
            "added_fields": self.added_fields,
            "dropped_fields": self.dropped_fields,
        }


# --------------------------------------------------------------------------- #
# client
# --------------------------------------------------------------------------- #

class FiscalDataClient:
    """Paginating, retrying client for the Treasury Fiscal Data API.

    The HTTP session is injected so the whole class is testable without a
    network: anything with a `.get(url, params=..., timeout=...)` returning an
    object with `.status_code`, `.json()` and `.raise_for_status()` will do.
    """

    def __init__(
        self,
        sources: dict | None = None,
        *,
        session: Any = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        timeout: int = DEFAULT_TIMEOUT,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.sources = sources or load_sources()
        self.base_url = self.sources["fiscaldata"]["base_url"].rstrip("/") + "/"
        page_size_max = self.sources["fiscaldata"].get("page_size_max", DEFAULT_PAGE_SIZE)
        self.page_size = min(page_size, page_size_max)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self._sleep = sleep

        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    # -- HTTP ------------------------------------------------------------- #

    def _get(self, url: str, params: dict) -> tuple[dict, int]:
        """One GET with bounded exponential backoff. Returns (payload, n_retries).

        Backoff is 2s, 4s, 8s, 16s. Retries cover transport faults and the status
        codes that mean "ask again"; a 4xx means the request itself is wrong and
        retrying it just delays the error by thirty seconds.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if attempt:
                self._sleep(self.backoff_base ** attempt)
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                status = getattr(resp, "status_code", 200)
                if status in RETRY_STATUS:
                    last_error = FiscalDataError(f"HTTP {status} from {url}")
                    continue
                resp.raise_for_status()
                return resp.json(), attempt
            except Exception as exc:  # noqa: BLE001 - re-raised below with context
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status not in RETRY_STATUS:
                    raise FiscalDataError(f"{url}: HTTP {status}") from exc
                last_error = exc

        raise FiscalDataError(
            f"{url}: giving up after {self.max_retries} retries"
        ) from last_error

    # -- fetch ------------------------------------------------------------ #

    def fetch(
        self,
        endpoint: str,
        *,
        fields: Iterable[str] | None = None,
        filters: Iterable[str] | str | None = None,
        sort: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
        enforce_contract: bool = True,
    ) -> FetchResult:
        """Retrieve every page of an endpoint as raw strings.

        Parameters
        ----------
        fields
            Restrict the response to these fields. Defaults to the contracted
            `expected_fields`, which keeps 114-column endpoints from being pulled
            in full. Pass an explicit list to widen it, or an empty list for an
            unrestricted pull — which is the only way field drift is visible,
            since a `fields=` request returns a subset by construction.
        filters
            Fiscal Data filter expressions, e.g. `"record_date:gte:2020-01-31"`.
        sort
            Sort expression; defaults to ascending on the endpoint's date field so
            page order is deterministic. Unstable ordering is what makes
            pagination silently skip rows.
        max_pages
            Stop early. For probing only — a truncated fetch is flagged on the
            result and must never be written as if complete.
        enforce_contract
            Raise if a contracted field is absent from the response.
        """
        spec = endpoint_spec(endpoint, self.sources)
        url = self.base_url + spec["path"]
        date_field = spec.get("date_field", "record_date")
        size = min(page_size or self.page_size,
                   self.sources["fiscaldata"].get("page_size_max", DEFAULT_PAGE_SIZE))

        if fields is None:
            fields = spec.get("expected_fields")
        field_list = list(fields) if fields else None

        base_params: dict[str, Any] = {"page[size]": size}
        if field_list:
            base_params["fields"] = ",".join(field_list)
        if filters:
            base_params["filter"] = (
                filters if isinstance(filters, str) else ",".join(filters)
            )
        base_params["sort"] = sort or date_field

        rows: list[dict] = []
        total_count: int | None = None
        total_pages: int | None = None
        n_retries = 0
        page = 1

        while True:
            params = dict(base_params, **{"page[number]": page})
            payload, retries = self._get(url, params)
            n_retries += retries

            meta = payload.get("meta", {})
            declared = meta.get("total-count")
            declared_pages = meta.get("total-pages")

            if total_count is None:
                total_count, total_pages = declared, declared_pages
            elif declared is not None and declared != total_count:
                raise PaginationError(
                    f"{endpoint}: total-count changed from {total_count} to "
                    f"{declared} while paginating (page {page}). The source was "
                    "republished mid-fetch; rows retrieved so far may double-count "
                    "or skip. Re-run the fetch."
                )

            batch = payload.get("data", [])
            rows.extend(batch)

            if max_pages is not None and page >= max_pages:
                break
            if total_pages is not None:
                if page >= total_pages:
                    break
            elif len(batch) < size:
                break
            page += 1

        truncated = max_pages is not None and total_pages is not None and page < total_pages
        if total_count is not None and not truncated and len(rows) != total_count:
            raise PaginationError(
                f"{endpoint}: retrieved {len(rows)} rows but the API declared "
                f"{total_count}. Pagination lost or duplicated data; refusing to "
                "return a frame that looks complete."
            )

        frame = pd.DataFrame(rows, dtype="object")
        observed = sorted(frame.columns)

        # A zero-row response carries no field names to check — that is a filter
        # that matched nothing, not a broken contract.
        if enforce_contract and not frame.empty:
            self._check_contract(endpoint, spec, observed, field_list)

        baseline = spec.get("observed_fields_at_probe") or []
        # Drift is only meaningful over an unrestricted pull; a `fields=` request
        # returns a subset by construction.
        if field_list:
            added = dropped = []
        else:
            added = sorted(set(observed) - set(baseline))
            dropped = sorted(set(baseline) - set(observed))

        return FetchResult(
            endpoint=endpoint,
            frame=frame,
            url=url,
            params=base_params,
            retrieval_date=pd.Timestamp.now("UTC"),
            total_count=total_count,
            n_pages=page,
            n_retries=n_retries,
            observed_fields=observed,
            added_fields=list(added),
            dropped_fields=list(dropped),
        )

    @staticmethod
    def _check_contract(
        endpoint: str,
        spec: dict,
        observed: list[str],
        requested: list[str] | None,
    ) -> None:
        """A contracted field that did not come back is a build failure."""
        contracted = set(spec.get("expected_fields") or [])
        # Only hold the response to fields that were actually asked for.
        if requested is not None:
            contracted &= set(requested)
        missing = sorted(contracted - set(observed))
        if missing:
            raise ContractBreak(
                f"{endpoint}: response is missing contracted field(s) {missing}. "
                "config/sources.yaml no longer describes this endpoint — re-run "
                "scripts/probe_sources.py and correct it before ingesting."
            )


# --------------------------------------------------------------------------- #
# typing and storage
# --------------------------------------------------------------------------- #

def parse_endpoint(
    result: FetchResult,
    sources: dict | None = None,
    *,
    country: str = "US",
) -> tuple[pd.DataFrame, ParseReport]:
    """Coerce a raw fetch using the schema declared in config.

    The schema comes from `config/sources.yaml`, never from the data and never
    from `meta.dataTypes` — an API that changes a field from CURRENCY to STRING
    should break the build, not quietly change how the column is read.
    """
    spec = endpoint_spec(result.endpoint, sources)
    schema = spec.get("schema") or {}
    present = {k: v for k, v in schema.items() if k in result.frame.columns}

    typed, report = parse_typed(
        result.frame.to_dict(orient="records"),
        present,
        endpoint=result.endpoint,
    )
    typed = add_provenance(
        typed,
        source=f"fiscaldata/{result.endpoint}",
        retrieval_date=result.retrieval_date,
        country=country,
    )
    return typed, report


def raw_path(
    endpoint: str,
    retrieval_date: pd.Timestamp,
    root: pathlib.Path | str = REPO_ROOT / "data" / "raw",
) -> pathlib.Path:
    """Where a raw pull lands. Partitioned by retrieval date, not observation date.

    Raw is an archive of what the API said and when it said it, so the same month
    retrieved twice is two records, not an overwrite. That is what makes a
    revision detectable rather than destructive.
    """
    stamp = pd.Timestamp(retrieval_date).strftime("%Y-%m-%d")
    return pathlib.Path(root) / "fiscaldata" / endpoint / f"retrieved={stamp}"


def write_raw(
    result: FetchResult,
    root: pathlib.Path | str = REPO_ROOT / "data" / "raw",
) -> pathlib.Path:
    """Write a fetch to parquet, exactly as retrieved, with its manifest.

    Values stay strings. Coercing on the way in would make the archive a record of
    what this code believed rather than of what the API returned, and there would
    be no way back to the original once a parse rule changed.
    """
    outdir = raw_path(result.endpoint, result.retrieval_date, root)
    outdir.mkdir(parents=True, exist_ok=True)

    frame = result.frame.astype("object") if not result.frame.empty else result.frame
    target = outdir / "part.parquet"
    frame.to_parquet(target, index=False)
    (outdir / "manifest.json").write_text(
        json.dumps(result.manifest(), indent=2), encoding="utf-8"
    )
    return target
