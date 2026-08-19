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

from scripts.probe_wam_reference import find_values


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
