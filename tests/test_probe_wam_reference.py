"""Matching Treasury's published average maturity against ours, without a network.

The hazard here is not a missing number, it is a number that MATCHES for the
wrong reason. Treasury quotes average maturity in months and the Treasury
Bulletin quotes average length for debt held by PRIVATE INVESTORS — a different
population that moves with Federal Reserve holdings. Converting units silently,
or ignoring the population, turns a definitional mismatch into an apparent
agreement, which is worse than finding nothing.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.probe_wam_reference import (document_date, find_values,
                                         reconcile, term_mentions)


def test_a_value_in_months_is_recorded_as_months():
    """71 months and 5.92 years are the same duration; only one is what was said."""
    hits = find_values(
        "The weighted average maturity of marketable debt outstanding was 71 "
        "months at the end of the quarter, broadly unchanged."
    )
    assert hits and hits[0]["value"] == 71.0
    assert hits[0]["unit"] == "month"


def test_a_value_in_years_is_recorded_as_years():
    hits = find_values("Average maturity stood at 5.9 years, near its historical high.")
    assert hits and hits[0]["unit"] == "year" and hits[0]["value"] == 5.9


def test_the_private_investor_population_is_flagged():
    """A different population, so a close match would be a coincidence."""
    hits = find_values(
        "The average length of the marketable debt held by private investors was "
        "68 months."
    )
    assert hits and hits[0]["population"] == "private investors"


def test_an_unstated_population_says_so_rather_than_assuming():
    hits = find_values("Weighted average maturity was 71 months.")
    assert hits and hits[0]["population"].startswith("unstated")


def test_units_are_never_normalised():
    """No hit may carry a converted value; the probe records what was written."""
    hits = find_values("Average maturity was 71 months.")
    assert all("years" not in h for h in hits)
    assert hits[0]["value"] == 71.0, "71 months must not become 5.92"


def test_a_chart_axis_does_not_yield_a_published_figure():
    hits = find_values(
        "Average Maturity 0 12 24 36 48 60 72 84 96 months 0 12 24 36 48 60 72 84"
    )
    assert all(h["rejected"] for h in hits)


def test_the_term_is_recorded_even_when_no_value_is_matched():
    """Zero values must be diagnosable.

    The first run read ODM's own deck and reported zero. That is two findings
    wearing one number — the document may not state a figure, or may state it in
    a shape the pattern misses — and without the raw mentions there is no way to
    tell which, or to improve.
    """
    text = ("Slide 12: Average Maturity of Marketable Debt Outstanding. "
            "See the chart for the current level.")
    assert not find_values(text)
    assert term_mentions(text), "the term appears and must be reported"


def test_mentions_are_capped_so_one_deck_cannot_flood_the_report():
    text = "average maturity " * 50
    assert len(term_mentions(text)) <= 6


# --------------------------------------------------------------------------- #
# Adjacency, dating, and the comparison itself
# --------------------------------------------------------------------------- #

def test_a_projection_horizon_is_not_a_level():
    """'over the next 10 years' produced a 10.0-year 'value' in a live run."""
    hits = find_values(
        "Using the above assumptions, over the next 10 years: average maturity "
        "of issuance settles."
    )
    assert all(h["rejected"] for h in hits)


def test_a_rate_shock_horizon_is_not_a_level():
    hits = find_values(
        "rates are shocked higher after 10 years relative to the base case; "
        "average maturity rises"
    )
    assert all(h["rejected"] for h in hits)


def test_a_stated_level_still_survives():
    for text in (
        "Average maturity of total debt outstanding rose to 69 months.",
        "the weighted average maturity of marketable debt was 71 months at quarter end",
    ):
        hits = find_values(text)
        assert hits and not hits[0]["rejected"], text


def test_the_publication_date_is_read_from_the_document_not_the_url():
    """ODM decks publish as '2nd Quarter' with no year in the address."""
    assert document_date("Office of Debt Management Presented to the TBAC "
                         "February 2, 2004 Slide 1") == "2004-02"
    assert document_date("Fiscal Year 2016 Mid-Session Review, August 2015") == "2015-08"


def test_an_undated_document_returns_none_rather_than_a_guess():
    assert document_date("Portfolio Metrics. Weighted Average Maturity.") is None


def test_units_are_converted_only_at_the_comparison():
    import pandas as pd

    wam = pd.DataFrame({"observation_date": [pd.Timestamp("2009-03-31")],
                        "wam_years": [4.0]})
    result = reconcile(
        [{"value": 60.0, "unit": "month", "population": "x", "document_date": "2009-03"}],
        wam,
    )
    assert result[0]["comparable"]
    assert result[0]["stated_months"] == 60.0 and result[0]["our_months"] == 48.0
    assert result[0]["difference_months"] == 12.0


def test_an_undated_value_is_never_paired_with_our_latest_month():
    """Pairing by position would manufacture a reconciliation from a coincidence."""
    import pandas as pd

    wam = pd.DataFrame({"observation_date": [pd.Timestamp("2026-07-31")],
                        "wam_years": [5.816]})
    result = reconcile(
        [{"value": 71.0, "unit": "month", "population": "x", "document_date": None}], wam
    )
    assert not result[0]["comparable"]
    assert "no date" in result[0]["why"]
