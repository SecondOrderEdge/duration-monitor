"""Tests for the Eurostat client and the euro-area normalization.

The risk here is arithmetic, not plumbing. JSON-stat delivers values as a flat
dictionary keyed by a row-major offset into the product of every dimension, so a
transposed decode attributes every number to the wrong country, instrument or
quarter while producing a perfectly well-formed table of plausible figures.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.ingestion.eurostat import EurostatError, decode_jsonstat
from src.transformation.normalize import (
    MILLIONS,
    NormalizationError,
    normalize_eurostat_debt,
)


def jsonstat(values: dict) -> dict:
    """Two countries x two instruments x two quarters, in declared order."""
    return {
        "id": ["geo", "na_item", "time"],
        "size": [2, 2, 2],
        "dimension": {
            "geo": {"category": {"index": {"DE": 0, "IT": 1}}},
            "na_item": {"category": {"index": {"F31": 0, "F32": 1}}},
            "time": {"category": {"index": {"2025-Q3": 0, "2025-Q4": 1}}},
        },
        "value": values,
    }


# --------------------------------------------------------------------------- #
# offset decoding
# --------------------------------------------------------------------------- #


def test_offsets_decode_to_the_right_cell():
    """Row-major: the LAST dimension varies fastest.

    Reverse it and DE's short-term figure becomes IT's long-term figure, with
    nothing in the output to show for it.
    """
    frame = decode_jsonstat(jsonstat({
        "0": 10.0,   # DE, F31, 2025-Q3
        "1": 11.0,   # DE, F31, 2025-Q4
        "2": 20.0,   # DE, F32, 2025-Q3
        "3": 21.0,   # DE, F32, 2025-Q4
        "4": 30.0,   # IT, F31, 2025-Q3
        "7": 41.0,   # IT, F32, 2025-Q4
    })).set_index(["geo", "na_item", "time"])["value"]

    assert frame.loc[("DE", "F31", "2025-Q3")] == 10.0
    assert frame.loc[("DE", "F32", "2025-Q4")] == 21.0
    assert frame.loc[("IT", "F31", "2025-Q3")] == 30.0
    assert frame.loc[("IT", "F32", "2025-Q4")] == 41.0


def test_sparse_responses_are_normal_not_an_error():
    """Eurostat omits cells rather than sending nulls."""
    frame = decode_jsonstat(jsonstat({"0": 1.0, "7": 2.0}))
    assert len(frame) == 2


def test_a_response_with_no_values_is_refused():
    with pytest.raises(EurostatError, match="no values"):
        decode_jsonstat(jsonstat({}))


def test_a_response_with_no_dimension_index_is_refused():
    payload = jsonstat({"0": 1.0})
    del payload["dimension"]["geo"]["category"]["index"]
    with pytest.raises(EurostatError, match="no category index"):
        decode_jsonstat(payload)


def test_mismatched_id_and_size_is_refused():
    payload = jsonstat({"0": 1.0})
    payload["size"] = [2, 2]
    with pytest.raises(EurostatError, match="dimension index"):
        decode_jsonstat(payload)


def test_category_order_follows_the_declared_index_not_dict_order():
    """The index values, not insertion order, define which position is which."""
    payload = jsonstat({"0": 5.0})
    payload["dimension"]["geo"]["category"]["index"] = {"IT": 0, "DE": 1}
    frame = decode_jsonstat(payload)
    assert frame.iloc[0]["geo"] == "IT"


# --------------------------------------------------------------------------- #
# normalization
# --------------------------------------------------------------------------- #


def decoded_rows() -> pd.DataFrame:
    return pd.DataFrame({
        "geo": ["DE"] * 4 + ["IT"] * 2,
        "na_item": ["F31", "F32", "F3", "F4", "F31", "F32"],
        "sector": ["S1311"] * 6,
        "unit": ["MIO_EUR"] * 6,
        "time": ["2025-Q4"] * 6,
        "value": [100.0, 900.0, 1000.0, 50.0, 300.0, 700.0],
    })


def test_only_the_two_maturity_classes_are_mapped():
    """F3 is their sum and would double-count; loans are not securities."""
    out = normalize_eurostat_debt(decoded_rows())
    de = out[out["country"] == "DE"].set_index("security_class")["amount_outstanding"]

    assert de["BILLS"] == pytest.approx(100.0 * MILLIONS)
    assert de["COUPONS"] == pytest.approx(900.0 * MILLIONS)
    assert de["TOTAL_MARKETABLE"] == pytest.approx(1000.0 * MILLIONS)  # 100 + 900, not F3


def test_the_total_is_flagged_as_derived():
    """The US total is published and independently checkable; this one is not.

    Passing a derived total off as a published one would make the reconciliation
    check look available when it cannot run.
    """
    out = normalize_eurostat_debt(decoded_rows())
    assert out.loc[out["security_class"] == "TOTAL_MARKETABLE", "total_is_derived"].all()
    assert not out.loc[out["security_class"] == "BILLS", "total_is_derived"].any()


def test_countries_are_kept_separate():
    out = normalize_eurostat_debt(decoded_rows())
    it = out[out["country"] == "IT"].set_index("security_class")["amount_outstanding"]
    assert it["TOTAL_MARKETABLE"] == pytest.approx(1000.0 * MILLIONS)
    assert set(out["country"]) == {"DE", "IT"}


def test_quarters_become_period_end_dates():
    out = normalize_eurostat_debt(decoded_rows())
    assert out["observation_date"].max() == pd.Timestamp("2025-12-31")


def test_the_wrong_sector_raises_rather_than_returning_nothing():
    """Central government, to match the US series. General government is a
    different denominator and would not be comparable."""
    with pytest.raises(NormalizationError, match="no rows for sector"):
        normalize_eurostat_debt(decoded_rows(), sector="S13")
