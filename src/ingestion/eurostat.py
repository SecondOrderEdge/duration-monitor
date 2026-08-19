"""Eurostat client, for the euro-area sovereigns.

Eurostat serves JSON-stat, whose values arrive as a FLAT dictionary keyed by a
single integer — the row-major offset into the product of every dimension. A
response with dimensions of size (1, 20, 8, 4, 3, 129) has 247,680 cells, and
cell 91,412 means something specific about one country, one instrument, one
sector, one unit and one quarter. Decode the offset wrongly and every number is
attributed to the wrong series while remaining a perfectly plausible figure in a
perfectly well-formed table.

So the decoding is done explicitly against the response's own `id` and `size`
lists rather than by assuming an order, and the reconstruction is checked: the
number of decoded observations must equal the number of values the response
carried, or the frame is refused.

Sparse responses are normal here — Eurostat omits cells rather than sending
nulls, so `value` is usually far smaller than the full product. That is expected
and is not the same thing as a decoding error, which is why the check is against
the count of values present rather than the size of the grid.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from .fiscaldata import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    RETRY_STATUS,
)

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"


class EurostatError(RuntimeError):
    """The response cannot be trusted to mean what it appears to mean."""


@dataclass
class EurostatResult:
    dataset: str
    frame: pd.DataFrame
    label: str | None
    updated: str | None
    retrieval_date: pd.Timestamp
    n_values: int = 0


def decode_jsonstat(payload: dict) -> pd.DataFrame:
    """Turn a JSON-stat response into a long DataFrame, one row per observation.

    The offset arithmetic is the whole of the risk. For dimensions of size
    (d0, d1, ... dn) the cell at index i belongs to category
    (i // stride_k) % d_k for each k, where stride_k is the product of the sizes
    to its right. Getting that backwards silently transposes the data.
    """
    dimension_ids = payload.get("id")
    sizes = payload.get("size")
    dimensions = payload.get("dimension") or {}
    values = payload.get("value") or {}

    if not dimension_ids or not sizes or len(dimension_ids) != len(sizes):
        raise EurostatError(
            f"response has no usable dimension index: id={dimension_ids}, size={sizes}"
        )
    if not values:
        raise EurostatError("response carried no values")

    # Category code per position, per dimension, ordered by the index the
    # response itself declares — never by dict insertion order.
    categories: list[list[str]] = []
    for dimension_id in dimension_ids:
        index = ((dimensions.get(dimension_id) or {}).get("category") or {}).get("index")
        if isinstance(index, dict):
            ordered = sorted(index, key=index.get)
        elif isinstance(index, list):
            ordered = list(index)
        else:
            raise EurostatError(f"dimension {dimension_id!r} has no category index")
        categories.append(ordered)

    strides = [1] * len(sizes)
    for position in range(len(sizes) - 2, -1, -1):
        strides[position] = strides[position + 1] * sizes[position + 1]

    records = []
    for offset, value in values.items():
        cell = int(offset)
        row = {}
        for position, dimension_id in enumerate(dimension_ids):
            category_index = (cell // strides[position]) % sizes[position]
            row[dimension_id] = categories[position][category_index]
        row["value"] = value
        records.append(row)

    frame = pd.DataFrame.from_records(records)
    if len(frame) != len(values):
        raise EurostatError(
            f"decoded {len(frame)} observations from {len(values)} values; "
            "the offset arithmetic does not reconstruct the response"
        )
    return frame


class EurostatClient:
    """Dataset puller. The session is injected so decoding is testable offline."""

    def __init__(
        self,
        *,
        session: Any = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        timeout: int = DEFAULT_TIMEOUT,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self._sleep = sleep
        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    def fetch(self, dataset: str, **filters) -> EurostatResult:
        """Fetch one dataset, filtered by dimension. Lists become repeated params."""
        params: list[tuple[str, str]] = [("format", "JSON"), ("lang", "EN")]
        for key, value in filters.items():
            if isinstance(value, (list, tuple, set)):
                params.extend((key, str(v)) for v in value)
            else:
                params.append((key, str(value)))

        url = BASE_URL + dataset
        last: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if attempt:
                self._sleep(self.backoff_base ** attempt)
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                status = getattr(response, "status_code", 200)
                if status in RETRY_STATUS:
                    last = EurostatError(f"HTTP {status}")
                    continue
                response.raise_for_status()
                payload = response.json()
                break
            except Exception as exc:  # noqa: BLE001
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status not in RETRY_STATUS:
                    raise EurostatError(f"{url}: HTTP {status}") from exc
                last = exc
        else:
            raise EurostatError(
                f"{url}: giving up after {self.max_retries} retries"
            ) from last

        frame = decode_jsonstat(payload)
        return EurostatResult(
            dataset=dataset,
            frame=frame,
            label=payload.get("label"),
            updated=payload.get("updated"),
            retrieval_date=pd.Timestamp.now("UTC"),
            n_values=len(payload.get("value") or {}),
        )
