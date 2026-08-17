"""Tests for the Treasury Fiscal Data client.

No network. The client takes an injected session, so every path — including the
ones that only happen when the API misbehaves — is exercised against a fake that
returns exactly the payload each test needs.

The cases that matter most are the silent ones: a short pagination and a dropped
field both produce a well-formed DataFrame that is simply wrong, so each has an
explicit test asserting that the client refuses rather than returns.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.ingestion.fiscaldata import (
    ContractBreak,
    FiscalDataClient,
    FiscalDataError,
    PaginationError,
    endpoint_spec,
    load_sources,
    parse_endpoint,
    raw_path,
    write_raw,
)

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


class HTTPError(Exception):
    """Mimics requests.HTTPError: carries a response with a status code."""

    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.response = FakeResponse({}, status_code)


class FakeSession:
    """Returns queued responses in order and records every call."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {}), "timeout": timeout})
        if not self._responses:
            raise AssertionError("FakeSession ran out of queued responses")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def page(rows: list[dict], total_count: int, total_pages: int) -> FakeResponse:
    return FakeResponse(
        {"data": rows, "meta": {"total-count": total_count, "total-pages": total_pages}}
    )


SOURCES = {
    "fiscaldata": {
        "base_url": "https://example.invalid/api/",
        "page_size_max": 100,
        "endpoints": {
            "demo": {
                "path": "v1/demo",
                "date_field": "record_date",
                "verified": True,
                "expected_fields": ["record_date", "security_class_desc", "total_mil_amt"],
                "observed_fields_at_probe": [
                    "record_date",
                    "security_class_desc",
                    "total_mil_amt",
                    "src_line_nbr",
                ],
                "schema": {
                    "record_date": "date",
                    "security_class_desc": "category",
                    "total_mil_amt": "decimal",
                },
            },
            "unverified": {
                "path": "v1/unverified",
                "verified": False,
                "expected_fields": ["record_date"],
            },
        },
    }
}


def row(date: str, cls: str = "Bills", amt: str = "1000.5") -> dict:
    return {"record_date": date, "security_class_desc": cls, "total_mil_amt": amt}


def client(responses: list, **kwargs) -> FiscalDataClient:
    return FiscalDataClient(
        SOURCES,
        session=FakeSession(responses),
        sleep=lambda _: None,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# config guards
# --------------------------------------------------------------------------- #


def test_unverified_endpoint_refuses_to_ingest():
    """An unconfirmed contract is a guess, and ingestion never runs on a guess."""
    with pytest.raises(ContractBreak, match="unverified"):
        endpoint_spec("unverified", SOURCES)


def test_unknown_endpoint_names_the_known_ones():
    with pytest.raises(KeyError, match="demo"):
        endpoint_spec("nope", SOURCES)


# --------------------------------------------------------------------------- #
# pagination
# --------------------------------------------------------------------------- #


def test_single_page_fetch():
    c = client([page([row("2024-01-31"), row("2024-02-29")], 2, 1)])
    result = c.fetch("demo", page_size=100)

    assert result.n_rows == 2
    assert result.n_pages == 1
    assert result.total_count == 2
    assert list(result.frame["record_date"]) == ["2024-01-31", "2024-02-29"]


def test_pagination_concatenates_every_page_in_order():
    c = client(
        [
            page([row("2024-01-31"), row("2024-02-29")], 5, 3),
            page([row("2024-03-31"), row("2024-04-30")], 5, 3),
            page([row("2024-05-31")], 5, 3),
        ]
    )
    result = c.fetch("demo", page_size=2)

    assert result.n_rows == 5
    assert result.n_pages == 3
    assert list(result.frame["record_date"]) == [
        "2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31",
    ]
    # page[number] must advance; a client that never increments it loops forever
    # on page 1 and returns duplicates that still total the right row count.
    assert [call["params"]["page[number]"] for call in c.session.calls] == [1, 2, 3]


def test_short_pagination_raises_rather_than_returning_a_plausible_frame():
    """The API declares 5 rows and delivers 3. That must fail, not round down.

    This is the failure this test exists for: three-fifths of the debt outstanding
    still computes a bill share, and the number looks entirely reasonable.
    """
    c = client(
        [
            page([row("2024-01-31"), row("2024-02-29")], 5, 2),
            page([row("2024-03-31")], 5, 2),
        ]
    )
    with pytest.raises(PaginationError, match="retrieved 3 rows.*declared 5"):
        c.fetch("demo", page_size=2)


def test_total_count_change_mid_pagination_aborts():
    """A republish between pages shifts every offset after it."""
    c = client(
        [
            page([row("2024-01-31")], 3, 3),
            page([row("2024-02-29")], 4, 4),  # source grew under us
        ]
    )
    with pytest.raises(PaginationError, match="total-count changed from 3 to 4"):
        c.fetch("demo", page_size=1)


def test_max_pages_truncates_without_tripping_the_completeness_check():
    c = client([page([row("2024-01-31")], 10, 10)])
    result = c.fetch("demo", page_size=1, max_pages=1)

    assert result.n_rows == 1
    assert result.total_count == 10  # recorded, so the caller can see it is partial


def test_pagination_stops_on_a_short_page_when_total_pages_is_absent():
    c = client(
        [
            FakeResponse({"data": [row("2024-01-31"), row("2024-02-29")], "meta": {}}),
            FakeResponse({"data": [row("2024-03-31")], "meta": {}}),
        ]
    )
    result = c.fetch("demo", page_size=2)
    assert result.n_rows == 3
    assert result.n_pages == 2


def test_empty_response_is_not_an_error():
    c = client([page([], 0, 0)])
    result = c.fetch("demo")
    assert result.n_rows == 0


# --------------------------------------------------------------------------- #
# request construction
# --------------------------------------------------------------------------- #


def test_fields_default_to_the_contract_and_sort_is_deterministic():
    c = client([page([row("2024-01-31")], 1, 1)])
    c.fetch("demo")

    params = c.session.calls[0]["params"]
    assert params["fields"] == "record_date,security_class_desc,total_mil_amt"
    # Unstable ordering is what makes pagination skip rows.
    assert params["sort"] == "record_date"


def test_filters_and_explicit_fields_are_passed_through():
    c = client([page([row("2024-01-31")], 1, 1)])
    c.fetch(
        "demo",
        fields=["record_date"],
        filters=["record_date:gte:2024-01-01", "record_date:lte:2024-12-31"],
        sort="-record_date",
    )

    params = c.session.calls[0]["params"]
    assert params["fields"] == "record_date"
    assert params["filter"] == "record_date:gte:2024-01-01,record_date:lte:2024-12-31"
    assert params["sort"] == "-record_date"


def test_page_size_is_capped_at_the_documented_maximum():
    c = client([page([row("2024-01-31")], 1, 1)])
    c.fetch("demo", page_size=99999)
    assert c.session.calls[0]["params"]["page[size]"] == 100


# --------------------------------------------------------------------------- #
# contract enforcement
# --------------------------------------------------------------------------- #


def test_missing_contracted_field_raises():
    """A dropped column becomes all-NaN downstream, which reads as missing data."""
    c = client([page([{"record_date": "2024-01-31", "total_mil_amt": "1000"}], 1, 1)])
    with pytest.raises(ContractBreak, match="security_class_desc"):
        c.fetch("demo")


def test_contract_is_only_enforced_over_requested_fields():
    c = client([page([{"record_date": "2024-01-31"}], 1, 1)])
    result = c.fetch("demo", fields=["record_date"])
    assert result.n_rows == 1


def test_contract_check_can_be_disabled_for_diagnostics():
    c = client([page([{"record_date": "2024-01-31"}], 1, 1)])
    result = c.fetch("demo", enforce_contract=False)
    assert result.n_rows == 1


def test_field_drift_is_reported_but_not_fatal():
    """A new column is worth seeing; it is not a reason to fail the refresh."""
    rows = [
        {
            "record_date": "2024-01-31",
            "security_class_desc": "Bills",
            "total_mil_amt": "1000",
            "brand_new_field": "x",
            # src_line_nbr was in the baseline and is not returned here
        }
    ]
    # `fields` defaults to the contract, which would mask drift by construction,
    # so an empty list asks for everything the endpoint returns.
    c = client([page(rows, 1, 1)])
    result = c.fetch("demo", fields=[])

    assert result.added_fields == ["brand_new_field"]
    assert result.dropped_fields == ["src_line_nbr"]


def test_drift_is_not_reported_on_a_field_restricted_pull():
    """A subset request must not look like the API dropped everything else."""
    c = client([page([row("2024-01-31")], 1, 1)])
    result = c.fetch("demo")           # defaults to the contracted subset
    assert result.dropped_fields == []


# --------------------------------------------------------------------------- #
# retry
# --------------------------------------------------------------------------- #


def test_retries_transient_status_then_succeeds():
    c = client(
        [
            FakeResponse({}, 503),
            FakeResponse({}, 429),
            page([row("2024-01-31")], 1, 1),
        ]
    )
    result = c.fetch("demo")
    assert result.n_rows == 1
    assert result.n_retries == 2


def test_backoff_is_exponential():
    slept: list[float] = []
    c = FiscalDataClient(
        SOURCES,
        session=FakeSession(
            [FakeResponse({}, 503), FakeResponse({}, 503), page([row("2024-01-31")], 1, 1)]
        ),
        sleep=slept.append,
    )
    c.fetch("demo")
    assert slept == [2.0, 4.0]


def test_client_error_is_not_retried():
    """A 404 is a bug in the request; retrying it four times just delays the error."""
    session = FakeSession([HTTPError(404), page([row("2024-01-31")], 1, 1)])
    c = FiscalDataClient(SOURCES, session=session, sleep=lambda _: None)

    with pytest.raises(FiscalDataError, match="HTTP 404"):
        c.fetch("demo")
    assert len(session.calls) == 1


def test_gives_up_after_max_retries():
    c = client([FakeResponse({}, 503)] * 10, max_retries=2)
    with pytest.raises(FiscalDataError, match="giving up after 2 retries"):
        c.fetch("demo")


def test_transport_failure_is_retried():
    c = client([ConnectionError("reset"), page([row("2024-01-31")], 1, 1)])
    result = c.fetch("demo")
    assert result.n_rows == 1
    assert result.n_retries == 1


# --------------------------------------------------------------------------- #
# typing
# --------------------------------------------------------------------------- #


def test_parse_endpoint_coerces_using_the_declared_schema():
    c = client(
        [
            page(
                [
                    row("2024-01-31", "Bills", "1000.5"),
                    row("2024-02-29", "Notes", "null"),
                ],
                2,
                1,
            )
        ]
    )
    result = c.fetch("demo")
    typed, report = parse_endpoint(result, SOURCES)

    assert typed["record_date"].dtype.kind == "M"
    assert typed["total_mil_amt"].dtype == "float64"
    assert typed["total_mil_amt"].iloc[0] == pytest.approx(1000.5)
    assert np.isnan(typed["total_mil_amt"].iloc[1])       # "null" → NaN
    assert report.fields["total_mil_amt"].n_null_tokens == 1
    assert report.total_parse_failures == 0
    assert report.ok


def test_parse_endpoint_stamps_provenance():
    c = client([page([row("2024-01-31")], 1, 1)])
    result = c.fetch("demo")
    typed, _ = parse_endpoint(result, SOURCES)

    assert typed["source"].iloc[0] == "fiscaldata/demo"
    assert typed["country"].iloc[0] == "US"
    assert typed["retrieval_date"].iloc[0] == result.retrieval_date


def test_parse_endpoint_counts_uncoercible_values():
    c = client([page([row("2024-01-31", "Bills", "not-a-number")], 1, 1)])
    result = c.fetch("demo")
    _, report = parse_endpoint(result, SOURCES)

    assert report.fields["total_mil_amt"].n_parse_failures == 1
    assert not report.ok


# --------------------------------------------------------------------------- #
# storage
# --------------------------------------------------------------------------- #


def test_raw_path_partitions_by_retrieval_date(tmp_path):
    p = raw_path("demo", pd.Timestamp("2026-08-17T12:00:00"), root=tmp_path)
    assert p == tmp_path / "fiscaldata" / "demo" / "retrieved=2026-08-17"


def test_write_raw_keeps_values_as_strings(tmp_path):
    """Raw is an archive of what the API said, not of what we made of it."""
    c = client([page([row("2024-01-31", "Bills", "1000.5")], 1, 1)])
    result = c.fetch("demo")

    target = write_raw(result, root=tmp_path)
    back = pd.read_parquet(target)

    assert back["total_mil_amt"].iloc[0] == "1000.5"     # string, not 1000.5
    assert back["record_date"].iloc[0] == "2024-01-31"


def test_write_raw_records_a_manifest(tmp_path):
    c = client([page([row("2024-01-31")], 1, 1)])
    result = c.fetch("demo")
    target = write_raw(result, root=tmp_path)

    manifest = json.loads((target.parent / "manifest.json").read_text())
    assert manifest["endpoint"] == "demo"
    assert manifest["n_rows"] == 1
    assert manifest["total_count_declared"] == 1
    assert manifest["url"].endswith("v1/demo")
    assert "retrieval_date" in manifest


def test_two_pulls_of_the_same_endpoint_do_not_overwrite_each_other(tmp_path):
    """Re-retrieval must be additive, or a revision silently replaces the original."""
    c1 = client([page([row("2024-01-31", "Bills", "1000")], 1, 1)])
    r1 = c1.fetch("demo")
    r1.retrieval_date = pd.Timestamp("2026-08-17T10:00:00")

    c2 = client([page([row("2024-01-31", "Bills", "1050")], 1, 1)])
    r2 = c2.fetch("demo")
    r2.retrieval_date = pd.Timestamp("2026-09-17T10:00:00")

    write_raw(r1, root=tmp_path)
    write_raw(r2, root=tmp_path)

    stored = sorted((tmp_path / "fiscaldata" / "demo").iterdir())
    assert [p.name for p in stored] == ["retrieved=2026-08-17", "retrieved=2026-09-17"]


# --------------------------------------------------------------------------- #
# the real config
# --------------------------------------------------------------------------- #


def test_shipped_config_is_internally_consistent():
    """Every contracted and typed field must appear in the probe's observed list.

    This is the test that catches a field name typed from memory into
    config/sources.yaml: if it was never observed in a live response, it does not
    belong in the contract.
    """
    sources = load_sources()
    problems = []

    for name, spec in sources["fiscaldata"]["endpoints"].items():
        observed = set(spec.get("observed_fields_at_probe") or [])
        if not observed:
            problems.append(f"{name}: no observed_fields_at_probe recorded")
            continue
        for key in ("expected_fields", "schema"):
            declared = set(spec.get(key) or [])
            unobserved = sorted(declared - observed)
            if unobserved:
                problems.append(f"{name}.{key}: never observed live: {unobserved}")

    assert not problems, "\n".join(problems)


def test_shipped_config_marks_probed_endpoints_verified():
    sources = load_sources()
    for name in sources["fiscaldata"]["endpoints"]:
        spec = endpoint_spec(name, sources)   # raises if unverified
        assert spec.get("coverage"), f"{name}: no coverage recorded"


def test_shipped_config_declares_a_type_for_every_contracted_field():
    """A contracted field with no declared type would be inferred by pandas."""
    sources = load_sources()
    for name, spec in sources["fiscaldata"]["endpoints"].items():
        contracted = set(spec.get("expected_fields") or [])
        typed = set(spec.get("schema") or [])
        assert not (contracted - typed), (
            f"{name}: contracted but untyped: {sorted(contracted - typed)}"
        )
