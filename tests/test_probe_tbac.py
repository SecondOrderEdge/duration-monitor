"""The TBAC probe's judgement, tested without a network.

The distinction under test is the whole point of the probe: "we searched and it
is not there" and "we never searched" are different findings that produce the
same zero, and reporting the second as the first would retire a claim on no
evidence at all.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.probe_tbac import classify_outcome, clean_html, find_claims


def test_a_stated_range_after_the_word_bill_is_found():
    hits = find_claims(
        "The Committee recommends that bills be maintained in a range of "
        "15 to 20 percent of marketable debt outstanding."
    )
    assert hits and hits[0]["range"] == [15, 20]
    assert hits[0]["matches_configured_band"]


def test_a_stated_range_before_the_word_bill_is_found_too():
    """The committee's phrasing order is not known in advance."""
    hits = find_claims("A 15-20% allocation to Treasury bills was discussed.")
    assert hits and hits[0]["matches_configured_band"]


def test_a_different_range_is_reported_but_not_treated_as_confirmation():
    hits = find_claims("bills should sit between 20 and 25 percent of the portfolio")
    assert hits and hits[0]["range"] == [20, 25]
    assert not hits[0]["matches_configured_band"]


def test_context_travels_with_the_hit_so_a_human_can_judge_it():
    """A regex must not decide whether a sentence is a recommendation."""
    text = ("Historically the share of bills has ranged from 15 to 20 percent, "
            "though the Committee expressed no view on a target.")
    hits = find_claims(text)
    assert hits and "expressed no view" in hits[0]["context"]


def test_nothing_searched_is_not_reported_as_nothing_found():
    outcome, detail = classify_outcome(0, [])
    assert outcome == "NOT REACHED"
    assert "not about TBAC" in detail


def test_searched_and_absent_is_reported_as_not_found():
    assert classify_outcome(12, [])[0] == "NOT FOUND"


def test_a_matching_range_is_evidence_and_still_asks_to_be_read():
    outcome, detail = classify_outcome(
        5, [{"hits": [{"matches_configured_band": True}]}]
    )
    assert outcome == "EVIDENCE FOUND"
    assert "not the same as the committee recommending it" in detail


def test_only_other_ranges_contradicts_rather_than_confirms():
    outcome, detail = classify_outcome(
        5, [{"hits": [{"matches_configured_band": False}]}]
    )
    assert outcome == "OTHER RANGES FOUND"
    assert "configured band is wrong" in detail


def test_script_and_style_bodies_do_not_become_searchable_text():
    """A percentage inside a script tag is not something TBAC wrote."""
    text = clean_html("<p>bills</p><script>var x='15 to 20 percent';</script>")
    assert "15 to 20" not in text
