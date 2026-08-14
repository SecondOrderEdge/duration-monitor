"""Tests for the typed parsing layer.

The API returns everything as strings. These tests pin down that a value which
cannot be coerced becomes NaN *and* is counted — a NaN nobody counted is how a
wrong average reaches a chart.
"""

import numpy as np
import pandas as pd
import pytest

from src.ingestion.typed import add_provenance, parse_typed

SCHEMA = {
    "record_date": "date",
    "security_class_desc": "category",
    "total_mil_amt": "decimal",
}


def test_string_values_are_coerced_to_declared_types():
    rows = [
        {"record_date": "2024-01-31", "security_class_desc": "Bills", "total_mil_amt": "1000.5"},
        {"record_date": "2024-02-29", "security_class_desc": "Notes", "total_mil_amt": "2000.25"},
    ]
    df, report = parse_typed(rows, SCHEMA, endpoint="mspd_table_1")

    assert pd.api.types.is_datetime64_any_dtype(df["record_date"])
    assert pd.api.types.is_numeric_dtype(df["total_mil_amt"])
    assert df["total_mil_amt"].sum() == pytest.approx(3000.75)
    assert report.ok


def test_string_null_token_becomes_nan_and_is_counted_separately():
    """An explicit null is expected data, not a parse failure."""
    rows = [
        {"record_date": "2024-01-31", "security_class_desc": "Bills", "total_mil_amt": "null"},
        {"record_date": "2024-02-29", "security_class_desc": "Notes", "total_mil_amt": "5"},
    ]
    df, report = parse_typed(rows, SCHEMA)

    assert np.isnan(df["total_mil_amt"].iloc[0])
    assert report.fields["total_mil_amt"].n_null_tokens == 1
    assert report.fields["total_mil_amt"].n_parse_failures == 0
    assert report.ok


def test_uncoercible_value_is_nan_and_counted_as_a_failure():
    rows = [
        {"record_date": "2024-01-31", "security_class_desc": "Bills", "total_mil_amt": "not a number"},
        {"record_date": "2024-02-29", "security_class_desc": "Notes", "total_mil_amt": "5"},
    ]
    df, report = parse_typed(rows, SCHEMA)

    assert np.isnan(df["total_mil_amt"].iloc[0])
    assert report.fields["total_mil_amt"].n_parse_failures == 1
    assert "'not a number'" in report.fields["total_mil_amt"].failure_examples
    assert not report.ok


def test_string_comparison_hazard_is_actually_removed():
    """The bug this layer exists to prevent: '1000' < '9' is True as strings."""
    rows = [
        {"record_date": "2024-01-31", "security_class_desc": "Bills", "total_mil_amt": "1000"},
        {"record_date": "2024-02-29", "security_class_desc": "Notes", "total_mil_amt": "9"},
    ]
    df, _ = parse_typed(rows, SCHEMA)
    assert df["total_mil_amt"].iloc[0] > df["total_mil_amt"].iloc[1]


class TestNumericCleaning:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1,234,567.89", 1234567.89),
            ("$1,000", 1000.0),
            ("12.5%", 12.5),
            ("(500)", -500.0),          # accounting negative
            ("(1,250.75)", -1250.75),
            ("  42  ", 42.0),
            ("-17.5", -17.5),
        ],
    )
    def test_presentation_characters_are_stripped(self, raw, expected):
        df, report = parse_typed([{"v": raw}], {"v": "decimal"})
        assert df["v"].iloc[0] == pytest.approx(expected)
        assert report.ok


class TestIntegerHandling:
    def test_whole_number_is_accepted(self):
        df, report = parse_typed([{"v": "42"}], {"v": "integer"})
        assert df["v"].iloc[0] == 42
        assert report.ok

    def test_fractional_value_fails_rather_than_truncating(self):
        """Silently turning 42.7 into 42 loses data without saying so."""
        df, report = parse_typed([{"v": "42.7"}], {"v": "integer"})
        assert np.isnan(df["v"].iloc[0])
        assert report.fields["v"].n_parse_failures == 1


class TestSchemaContract:
    def test_missing_declared_field_is_reported(self):
        rows = [{"record_date": "2024-01-31", "security_class_desc": "Bills"}]
        _, report = parse_typed(rows, SCHEMA)

        assert report.missing_fields == ["total_mil_amt"]
        assert not report.ok

    def test_missing_field_raises_on_demand(self):
        rows = [{"record_date": "2024-01-31", "security_class_desc": "Bills"}]
        _, report = parse_typed(rows, SCHEMA, endpoint="mspd_table_1")

        with pytest.raises(ValueError, match="missing declared field"):
            report.raise_if_failed()

    def test_undeclared_field_is_carried_through_not_dropped(self):
        rows = [{"v": "1", "surprise_new_column": "x"}]
        df, report = parse_typed(rows, {"v": "decimal"})

        assert report.extra_fields == ["surprise_new_column"]
        assert "surprise_new_column" in df.columns  # visible, not silently lost

    def test_strict_mode_rejects_an_undeclared_field(self):
        rows = [{"v": "1", "surprise_new_column": "x"}]
        with pytest.raises(ValueError, match="undeclared field"):
            parse_typed(rows, {"v": "decimal"}, allow_extra=False)

    def test_unknown_declared_type_is_rejected(self):
        with pytest.raises(ValueError, match="unknown type"):
            parse_typed([{"v": "1"}], {"v": "float64"})

    def test_empty_response_yields_an_empty_frame_with_schema_columns(self):
        df, report = parse_typed([], SCHEMA)
        assert list(df.columns) == list(SCHEMA)
        assert len(df) == 0
        assert report.ok


class TestReporting:
    def test_report_frame_is_tabular_for_the_data_quality_page(self):
        rows = [{"v": "bad"}, {"v": "1"}]
        _, report = parse_typed(rows, {"v": "decimal"}, endpoint="auctions_query")
        frame = report.to_frame()

        assert frame["endpoint"].iloc[0] == "auctions_query"
        assert frame["n_parse_failures"].iloc[0] == 1

    def test_total_parse_failures_aggregates_across_fields(self):
        rows = [{"a": "bad", "b": "worse"}]
        _, report = parse_typed(rows, {"a": "decimal", "b": "decimal"})
        assert report.total_parse_failures == 2

    def test_clean_response_does_not_raise(self):
        rows = [{"v": "1"}, {"v": "2"}]
        _, report = parse_typed(rows, {"v": "decimal"})
        report.raise_if_failed()  # must not raise


class TestProvenance:
    def test_every_row_is_stamped(self):
        df = pd.DataFrame({"v": [1.0, 2.0]})
        out = add_provenance(
            df,
            source="mspd_table_1",
            retrieval_date=pd.Timestamp("2026-08-14"),
            publication_date=pd.Timestamp("2026-08-12"),
        )

        assert (out["source"] == "mspd_table_1").all()
        assert (out["country"] == "US").all()
        assert (out["retrieval_date"] == pd.Timestamp("2026-08-14")).all()
        assert (out["publication_date"] == pd.Timestamp("2026-08-12")).all()

    def test_publication_date_is_omitted_when_not_supplied(self):
        """Not every feed has a meaningful publication lag; absent beats invented."""
        out = add_provenance(
            pd.DataFrame({"v": [1.0]}),
            source="fred",
            retrieval_date=pd.Timestamp("2026-08-14"),
        )
        assert "publication_date" not in out.columns

    def test_input_frame_is_not_mutated(self):
        df = pd.DataFrame({"v": [1.0]})
        add_provenance(df, source="x", retrieval_date=pd.Timestamp("2026-08-14"))
        assert list(df.columns) == ["v"]
