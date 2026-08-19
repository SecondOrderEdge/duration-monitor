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

from scripts.probe_tbac import (classify_outcome, clean_html, find_claims,
                                links_from, year_of)


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


# --------------------------------------------------------------------------- #
# Link discovery — the first run's actual defect
# --------------------------------------------------------------------------- #

PAGE = b"""
<a href="/system/files/221/TBACCharge1Q32026.pdf">TBAC Presentation (Charge 1)</a>
<a href="/system/files/221/CombinedCharges-08152011.pdf">2011 - 3rd Quarter</a>
<a href="/news/press-releases/sb0591">TBAC Report to Secretary</a>
<a href="/policy-issues/financing-the-government/quarterly-refunding/quarterly-refunding-archives/2015">2015 Archives</a>
<a href="/about/careers">Careers at Treasury</a>
<a href="https://www.federalreserve.gov/whatever.pdf">2016 - 1st Quarter</a>
"""


def test_a_dated_link_is_followed_even_without_a_tbac_word():
    """The exact miss: the archive labels quarters by DATE, not by committee."""
    documents, _ = links_from("https://home.treasury.gov/x", PAGE)
    urls = [d["url"] for d in documents]
    assert any("CombinedCharges-08152011.pdf" in u for u in urls)


def test_named_tbac_documents_are_still_found():
    documents, _ = links_from("https://home.treasury.gov/x", PAGE)
    urls = [d["url"] for d in documents]
    assert any("TBACCharge1Q32026.pdf" in u for u in urls)
    assert any("sb0591" in u for u in urls)


def test_archive_pages_are_returned_as_indexes_not_documents():
    documents, indexes = links_from("https://home.treasury.gov/x", PAGE)
    assert any("2015" in i["url"] for i in indexes)
    assert not any("quarterly-refunding-archives/2015" in d["url"] for d in documents)


def test_unrelated_and_offsite_links_are_ignored():
    """A dated PDF on another host is not the committee's word."""
    documents, indexes = links_from("https://home.treasury.gov/x", PAGE)
    everything = [e["url"] for e in documents + indexes]
    assert not any("careers" in u for u in everything)
    assert not any("federalreserve.gov" in u for u in everything)


def test_year_is_read_from_the_url_when_the_label_has_none():
    assert year_of({"label": "Charge 1", "url": ".../CombinedCharges-08152011.pdf"}) == "2011"


def test_year_falls_back_to_unknown_rather_than_guessing():
    assert year_of({"label": "Charge 1", "url": "https://x/doc.pdf"}) is None
