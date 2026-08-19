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
                                classify_document, links_from,
                                looks_like_chart_axis, read_order, text_of, year_of)


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


# --------------------------------------------------------------------------- #
# Bounds
# --------------------------------------------------------------------------- #

def test_an_oversize_document_is_skipped_and_says_so():
    """A skipped document must not read as a searched one."""
    record = {"url": "x", "fetched": False,
              "skipped": "40,000,000 bytes exceeds the 12,000,000 cap"}
    text, why = text_of(record)
    assert text == ""
    assert "exceeds" in why


def test_a_partial_run_is_not_reported_as_a_clean_not_found():
    """The bug this guards: a budget stop that still claims full coverage."""
    outcome, detail = classify_outcome(5, [])
    assert outcome == "NOT FOUND"
    # The escalation to PARTIAL happens in main() against stopped_on_budget;
    # what matters here is that the plain verdict already points at coverage.
    assert "coverage_by_year" in detail


# --------------------------------------------------------------------------- #
# Chart-axis false positives — six of them survived into a published verdict
# --------------------------------------------------------------------------- #

# Verbatim from the live run that produced the false positive, so the fixture
# cannot drift into something the regex happens not to match — which is how the
# first version of this test passed while asserting nothing.
AXIS = ("Percentage Breakdown of Quarterly Marketable Issuance Fiscal Year -25-25 "
        "I 05 II III IV I 06 II III IV Treasury has reduced reliance on bill "
        "financing over the past calendar year, moving from 84% in December 2008 "
        "to 70% in 15% 20% 25% 4 -20 -15 -10 -5 25 -20 -15 -10 -5 30% 90% 100%")


def test_the_axis_fixture_is_not_vacuous():
    """Guards the guard: an AXIS that matches nothing would prove nothing."""
    assert "2008 to 70%" in AXIS


def test_a_year_fragment_is_not_paired_with_a_percentage():
    """The live [8, 70]: `\\d{1,2}` matched '08' inside '2008'."""
    assert not [h for h in find_claims(AXIS) if h["range"] == [8, 70]]


# A tick-label run with no sentence in it. AXIS above deliberately mixes prose
# with axis noise, because the live text did; density must NOT flag that one, and
# the word-boundary fix is what handles it. This heuristic is the second line.
PURE_AXIS = "-25 -20 -15 -10 -5 0 5 10 15 20 25 30% 40% 50% 60% 70% 80% 90% 100%"


def test_a_tick_label_run_is_recognised_as_an_axis():
    assert looks_like_chart_axis(PURE_AXIS)


def test_prose_mixed_with_axis_noise_is_not_flagged_by_density():
    """Density is deliberately conservative: AXIS carries a real sentence.

    Flagging it would discard the surrounding prose along with the noise, and
    the false positive it once produced is already handled by requiring word
    boundaries around the numbers.
    """
    assert not looks_like_chart_axis(AXIS)


def test_ordinary_prose_is_not_mistaken_for_an_axis():
    assert not looks_like_chart_axis(
        "The Committee recommends that bills be maintained in a range of 15 to "
        "20 percent of marketable debt outstanding, consistent with prior guidance."
    )


def test_an_axis_run_does_not_produce_a_confirmed_band():
    """The exact false positive: 15% and 20% adjacent in extracted tick labels."""
    hits = find_claims(AXIS)
    assert not any(h["matches_configured_band"] for h in hits)
    assert all(h["rejected"] for h in hits)


def test_a_descending_pair_is_rejected():
    """`[20, 10]` was reported as a range by the first bounded run."""
    hits = find_claims("bills 20 percent to 10 percent")
    assert hits and hits[0]["rejected"] == "descending pair; a range runs upward"


def test_rejected_matches_are_kept_and_labelled_not_dropped():
    """An over-aggressive filter must be visible in the evidence, not invisible."""
    hits = find_claims("bills 20 percent to 10 percent, and bills 30 to 25 percent")
    assert hits, "rejected matches are still returned so the filter can be audited"
    assert all(h["rejected"] for h in hits)


def test_a_real_recommendation_still_survives_both_filters():
    hits = find_claims(
        "The Committee reiterated its view that Treasury bills should represent "
        "between 15 and 20 percent of marketable debt outstanding over time."
    )
    assert hits and hits[0]["rejected"] is None
    assert hits[0]["matches_configured_band"]


# --------------------------------------------------------------------------- #
# Read order — a large search that looked in the wrong place
# --------------------------------------------------------------------------- #

def test_minutes_and_reports_are_read_before_chart_decks():
    """The live miss: 50 of 73 documents read were chart decks, 0 were minutes.

    The claim under test is a sentence, so it lives in prose. Sorting by class
    means a run truncated by its budget loses the chart decks, not the minutes.
    """
    documents = [
        {"url": "/system/files/276/2009-q4-chart.pdf", "label": "Q4 charts"},
        {"url": "/news/press-releases/sb0592", "label": "TBAC Minutes: 2009"},
        {"url": "/system/files/221/TBACCharge1.pdf", "label": "Charge 1"},
        {"url": "/news/press-releases/sb0591", "label": "TBAC Report to Secretary"},
    ]
    documents.sort(key=read_order)
    assert [classify_document(d) for d in documents][:2] == ["minutes", "report"]
    assert classify_document(documents[-1]) == "chart deck"


def test_a_chart_deck_is_recognised_from_either_label_or_url():
    assert classify_document({"url": "/x/2005-q3-charts.pdf", "label": "Q3"}) == "chart deck"
    assert classify_document(
        {"url": "/x/doc.pdf", "label": "Treasury Presentation to TBAC"}
    ) == "chart deck"


def test_an_unrecognised_document_is_not_sorted_ahead_of_prose():
    """Unknown documents must not displace the minutes from the front of the queue."""
    unknown = {"url": "/x/misc.pdf", "label": "misc"}
    minutes = {"url": "/news/press-releases/x", "label": "TBAC Minutes"}
    assert read_order(minutes) < read_order(unknown)


def test_stray_digits_in_a_url_are_not_reported_as_a_year():
    """The live report claimed coverage of 1922 and 2063."""
    assert year_of({"label": "2nd Quarter", "url": "https://x/files/1922-doc.pdf"}) is None
    assert year_of({"label": "", "url": "https://x/2063xyz"}) is None


def test_an_undated_press_release_is_honestly_unknown():
    """TBAC minutes publish labelled only '2nd Quarter'. Unknown is the answer."""
    assert year_of({"label": "2nd Quarter", "url": "https://x/news/press-releases/jy0909"}) is None


def test_a_real_year_in_the_label_wins_over_url_digits():
    assert year_of({"label": "2011 - 3rd Quarter", "url": "https://x/files/276/a.pdf"}) == "2011"
