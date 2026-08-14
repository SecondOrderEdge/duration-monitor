"""Typed parsing for string-valued API responses.

The Treasury fiscal data API returns every value as a string, and nulls as the
literal string `"null"`. Handing that to `pd.DataFrame` and letting pandas infer
types produces object columns full of strings that compare, sort and aggregate
wrongly while looking entirely normal — `"1000" < "9"` is True, and a column of
numeric strings sums by concatenation or raises depending on context.

So coercion is declared per field, never inferred, and every failure is counted.
A value that will not coerce becomes NaN **and** increments a counter that
surfaces on the Data Quality page. Silent coercion failure is the standard way a
wrong number reaches a dashboard: the column looks fine, a handful of rows are
quietly NaN, and an average shifts.

Nothing here knows any actual field names — those come from `config/sources.yaml`
once the source probe has confirmed them against live responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Strings the fiscal data API uses to mean "no value". Compared case-insensitively
# after stripping whitespace.
NULL_TOKENS = frozenset({"null", "none", "", "n/a", "na", "-", "*"})

VALID_TYPES = frozenset({"date", "decimal", "integer", "string", "category"})


@dataclass
class FieldReport:
    """Coercion outcome for a single field."""

    name: str
    dtype: str
    n_rows: int = 0
    n_null_tokens: int = 0      # explicit nulls: expected, not a problem
    n_parse_failures: int = 0   # present but uncoercible: a real problem
    failure_examples: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.n_parse_failures == 0


@dataclass
class ParseReport:
    """Coercion outcome for a whole response."""

    endpoint: str
    fields: dict[str, FieldReport] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    extra_fields: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing_fields and all(f.ok for f in self.fields.values())

    @property
    def total_parse_failures(self) -> int:
        return sum(f.n_parse_failures for f in self.fields.values())

    def to_frame(self) -> pd.DataFrame:
        """Tabular form for the Data Quality page."""
        return pd.DataFrame(
            [
                {
                    "endpoint": self.endpoint,
                    "field": f.name,
                    "dtype": f.dtype,
                    "n_rows": f.n_rows,
                    "n_null_tokens": f.n_null_tokens,
                    "n_parse_failures": f.n_parse_failures,
                    "failure_examples": "; ".join(f.failure_examples[:3]),
                }
                for f in self.fields.values()
            ]
        )

    def raise_if_failed(self) -> None:
        """Fail loudly. Called by the refresh workflow, not by the app."""
        if self.missing_fields:
            raise ValueError(
                f"{self.endpoint}: response is missing declared field(s) "
                f"{self.missing_fields}; the contract in config/sources.yaml no "
                "longer matches the API"
            )
        broken = {n: f.failure_examples[:3] for n, f in self.fields.items() if not f.ok}
        if broken:
            raise ValueError(f"{self.endpoint}: uncoercible values in {broken}")


def _is_null_token(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and np.isnan(value):
        return True
    if isinstance(value, str):
        return value.strip().lower() in NULL_TOKENS
    return False


def _clean_numeric(text: str) -> str:
    """Strip the presentation characters that appear in published figures.

    Handles thousands separators, currency symbols, percent signs, and the
    accounting convention of writing negatives in parentheses.
    """
    text = text.strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    for char in (",", "$", "%", " "):
        text = text.replace(char, "")
    return f"-{text}" if negative and text else text


def _coerce_value(value, dtype: str):
    """Coerce one value. Returns (result, failed)."""
    if _is_null_token(value):
        return (pd.NaT if dtype == "date" else np.nan), False

    try:
        if dtype in {"string", "category"}:
            return str(value).strip(), False

        if dtype == "date":
            parsed = pd.to_datetime(value, errors="raise")
            return parsed, False

        text = _clean_numeric(str(value))
        if text in {"", "-"}:
            return np.nan, False

        if dtype == "decimal":
            return float(text), False

        # integer: reject a value that would silently lose precision, rather
        # than truncating it.
        as_float = float(text)
        if not float(as_float).is_integer():
            return np.nan, True
        return as_float, False
    except (ValueError, TypeError, pd.errors.ParserError):
        return (pd.NaT if dtype == "date" else np.nan), True


def parse_typed(
    rows: list[dict],
    schema: dict[str, str],
    *,
    endpoint: str = "unknown",
    allow_extra: bool = True,
) -> tuple[pd.DataFrame, ParseReport]:
    """Coerce string-valued rows into a typed DataFrame.

    Parameters
    ----------
    rows
        Response records, as returned by the API.
    schema
        Field name to declared type: 'date', 'decimal', 'integer', 'string' or
        'category'. Fields absent from the schema are passed through untouched
        (or rejected, if `allow_extra` is False).
    endpoint
        Recorded on the report so failures can be attributed to a source.
    allow_extra
        Whether fields not in the schema are permitted. False is the strict mode
        used by the refresh workflow, where a new column means the API changed.

    Returns
    -------
    (DataFrame, ParseReport). The report is not optional — the caller decides
    whether to raise, but cannot avoid being told.
    """
    bad_types = {k: v for k, v in schema.items() if v not in VALID_TYPES}
    if bad_types:
        raise ValueError(
            f"unknown type(s) {bad_types}; valid types are {sorted(VALID_TYPES)}"
        )

    report = ParseReport(endpoint=endpoint)

    observed = set()
    for row in rows:
        observed.update(row.keys())

    report.missing_fields = sorted(set(schema) - observed) if rows else []
    report.extra_fields = sorted(observed - set(schema))

    if not allow_extra and report.extra_fields:
        raise ValueError(
            f"{endpoint}: response carries undeclared field(s) "
            f"{report.extra_fields}; the API has changed"
        )

    if not rows:
        empty = pd.DataFrame({name: pd.Series(dtype="object") for name in schema})
        return empty, report

    frame = pd.DataFrame(rows)
    out = {}

    for name, dtype in schema.items():
        fr = FieldReport(name=name, dtype=dtype)
        if name not in frame.columns:
            report.fields[name] = fr
            continue

        raw = frame[name]
        fr.n_rows = len(raw)

        values, failures = [], []
        for value in raw:
            if _is_null_token(value):
                fr.n_null_tokens += 1
            coerced, failed = _coerce_value(value, dtype)
            if failed:
                fr.n_parse_failures += 1
                if len(failures) < 5:
                    failures.append(repr(value))
            values.append(coerced)

        fr.failure_examples = failures
        report.fields[name] = fr

        if dtype == "date":
            out[name] = pd.to_datetime(pd.Series(values, index=raw.index))
        elif dtype == "category":
            out[name] = pd.Series(values, index=raw.index, dtype="object").astype(
                "category"
            )
        elif dtype == "string":
            out[name] = pd.Series(values, index=raw.index, dtype="object")
        else:
            out[name] = pd.Series(values, index=raw.index, dtype="float64")

    typed = pd.DataFrame(out, index=frame.index)

    # Undeclared fields are carried through as-is rather than dropped: losing a
    # column the probe has not yet accounted for would hide it.
    if allow_extra:
        for name in report.extra_fields:
            typed[name] = frame[name]

    return typed, report


def add_provenance(
    df: pd.DataFrame,
    *,
    source: str,
    retrieval_date: pd.Timestamp,
    country: str = "US",
    publication_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Stamp provenance onto every row.

    Every stored row carries where it came from and when it was retrieved.
    `publication_date` is separate from the observation date on purpose: MSPD for
    a given month end is not public until roughly the eighth business day of the
    following month, and a signal that ignores that gap is using information
    before it existed (Deviation D4).
    """
    out = df.copy()
    out["country"] = country
    out["source"] = source
    out["retrieval_date"] = pd.Timestamp(retrieval_date)
    if publication_date is not None:
        out["publication_date"] = pd.Timestamp(publication_date)
    return out
