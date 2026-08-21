"""Find Treasury's own published average maturity, to reconcile ours against.

`build_wam` computes 5.82 years from per-security MSPD detail. Nothing checks it
against what Treasury itself publishes, so a systematic error in the maturity
weighting would look exactly like a correct answer.

The Fiscal Data API does not carry it — probed 2026-08-19 across mspd_table_2
through _5 and avg_interest_rates, and no field reports an average maturity or
length. The figure lives in the Office of Debt Management's quarterly refunding
presentation, so that is what this reads.

THREE DEFINITIONS ARE IN PLAY and they are not interchangeable:

  ours                 all marketable, par basis, final maturity for FRN/TIPS
  ODM "average         all marketable, usually quoted in MONTHS
  maturity"
  Treasury Bulletin    marketable held by PRIVATE INVESTORS — excludes Federal
  "average length"     Reserve holdings, so it moves with SOMA, not just issuance

A number that matches ours is only reassuring if it is the first or second. The
third should differ, and by how much is itself informative. So every hit records
the units it was stated in and the surrounding phrase, and nothing is converted
automatically — silently turning 71 months into 5.92 years is how a definitional
mismatch becomes an apparent agreement.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.probe_tbac import (  # noqa: E402
    ENTRY_POINTS,
    fetch,
    links_from,
    looks_like_chart_axis,
    text_of,
)

# Every mention of the term, whether or not a value was matched near it.
# The first run read ODM's own deck — 55,807 characters — and reported zero
# values, which is two completely different findings wearing one number: the
# document may not state it, or it may state it in a shape the pattern misses.
# Without the raw mentions there is no way to tell, and no way to improve.
TERM = re.compile(r"average[- ]maturity|weighted[- ]average[- ]maturity|average[- ]length|\bWAM\b", re.I)


def term_mentions(text: str, *, window: int = 200, limit: int = 6) -> list[str]:
    """Snippets around the term itself, so a zero can be diagnosed."""
    out = []
    for match in TERM.finditer(text):
        start = max(match.start() - window, 0)
        out.append(" ".join(text[start:match.end() + window].split()))
        if len(out) >= limit:
            break
    return out

OUT_DIR = REPO_ROOT / "docs" / "source_probe" / "wam_reference"

# "average maturity of 71 months", "weighted average maturity was 5.9 years",
# "average length of the marketable debt ... 71 months".
_TERM = r"(?:weighted[- ]average[- ]maturity|average[- ]maturity|average[- ]length)"
_NUM = r"\b(\d{1,3}(?:\.\d{1,2})?)\s*(months?|years?|yrs?)\b"

# ADJACENCY, not proximity. A 160-character window let projection language pair
# with the term — "over the next 10 years", "shocked higher after 10 years" —
# and most of the twenty values the first successful run returned were that.
# 60 characters is about the length of the linking clause in "average maturity
# of total debt outstanding rose to 69 months".
VALUE_NEAR_WAM = re.compile(
    rf"{_TERM}[^.]{{0,60}}?{_NUM}|{_NUM}[^.]{{0,60}}?{_TERM}", re.I | re.S
)

# Phrases that make a nearby number a horizon or a shock, never a level. These
# appear BETWEEN the term and the number in exactly the false positives seen.
NOT_A_LEVEL = re.compile(
    r"\b(?:next|over the|after|within|shocked|scenario|projection|forecast|"
    r"assum\w*|hypothetical)\b", re.I
)

# Publication dates as ODM writes them on a cover slide or in a caption.
DATE_PATTERNS = [
    re.compile(r"\b(January|February|March|April|May|June|July|August|September|"
               r"October|November|December)\s+(\d{1,2}),\s*((?:19|20)\d{2})\b", re.I),
    re.compile(r"\b(January|February|March|April|May|June|July|August|September|"
               r"October|November|December)\s+((?:19|20)\d{2})\b", re.I),
]
MONTH_NUMBER = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}


def document_date(text: str, *, head: int = 4000) -> str | None:
    """Publication month, read from inside the document.

    ODM decks and TBAC minutes publish under labels like "2nd Quarter" with no
    year in the URL or the link text, which left every citation from the TBAC
    probe undated. The date IS in the document — on the cover slide, in "as of
    April 17, 2009" — so it is read from the content rather than guessed from
    the address. Returns YYYY-MM, or None rather than a guess.
    """
    window = text[:head]
    for pattern in DATE_PATTERNS:
        match = pattern.search(window)
        if match:
            groups = match.groups()
            month = MONTH_NUMBER[groups[0].lower()]
            year = groups[-1]
            return f"{year}-{month:02d}"
    return None

# Which population the sentence is about. Left unresolved rather than guessed:
# the distinction decides whether a match is a check or a different measurement.
PRIVATE_INVESTORS = re.compile(r"private investors?|held by the public", re.I)

# The fifth metric, and the one most likely to be mistaken for ours. ODM prints
# "Average Maturity of Issuance" and "Average Maturity of Marketable Debt
# Outstanding" ON THE SAME SLIDE. New issues are longer-dated than the stock, so
# the two differ by twenty months or more — the 77 and 78 month values a live run
# returned are issuance, against an outstanding stock nearer 50.
OF_ISSUANCE = re.compile(r"maturity of (?:marketable )?issuance|issuance\s*1/", re.I)
OF_OUTSTANDING = re.compile(
    r"maturity of (?:the )?(?:total|marketable)?\s*debt outstanding"
    r"|maturity of marketable debt|debt outstanding", re.I
)

# Projected and hypothetical figures share the slide with actual ones.
FORWARD_LOOKING = re.compile(r"project\w*|hypothetical|would lead|expected to", re.I)


def classify_metric(context: str) -> str:
    """Which of Treasury's average-maturity series a match belongs to."""
    if OF_ISSUANCE.search(context):
        return "average maturity of ISSUANCE — not our measurement"
    if OF_OUTSTANDING.search(context):
        return "average maturity of debt OUTSTANDING — comparable to ours"
    return "unstated — which series is unclear, do not compare"


def find_values(text: str, *, window: int = 300) -> list[dict]:
    """Stated average-maturity values, with units and population, unconverted."""
    hits = []
    for match in VALUE_NEAR_WAM.finditer(text):
        groups = [g for g in match.groups() if g is not None]
        if len(groups) < 2:
            continue
        value, unit = groups[0], groups[1].lower().rstrip("s")
        start = max(match.start() - window, 0)
        context = text[start:match.end() + window].strip()

        # The match text, PLUS the run-up to it. When the number comes first —
        # "over the next 10 years: average maturity of issuance settles" — the
        # disqualifying phrase sits before the number, outside the match, and
        # checking only the match let that straight through.
        lead_in = text[max(match.start() - 40, 0):match.start()]
        between = lead_in + match.group(0)
        rejected = None
        if looks_like_chart_axis(context):
            rejected = "surroundings read as chart axis labels, not prose"
        elif NOT_A_LEVEL.search(between):
            rejected = "the number is a horizon or a scenario, not a level"
        elif FORWARD_LOOKING.search(context):
            rejected = "the slide is a projection or a hypothetical, not an actual"

        metric = classify_metric(context)
        if rejected is None and not metric.startswith("average maturity of debt"):
            rejected = metric

        hits.append({
            "value": float(value),
            # Units are RECORDED, never normalised. 71 months and 5.92 years are
            # the same duration, and quietly converting one into the other is how
            # a reader stops noticing which definition they are looking at.
            "unit": "month" if unit.startswith(("month", "mo")) else "year",
            "population": ("private investors" if PRIVATE_INVESTORS.search(context)
                           else "unstated — assume all marketable, but check"),
            "metric": metric,
            "rejected": rejected,
            "context": context,
        })
        if len(hits) >= 40:
            break
    return hits


def reconcile(stated: list[dict], wam: "pd.DataFrame") -> list[dict]:
    """Compare each dated stated value against our WAM for the same month.

    Units are converted HERE and only here, at the point of comparison, with both
    the original and the converted figure carried on the result. Converting at
    extraction would have made 71 months and 5.92 years indistinguishable in the
    evidence, which is the whole reason units are recorded verbatim upstream.

    A stated value with no date is not compared. There is nothing to compare it
    to, and pairing it with our latest month would manufacture a reconciliation
    out of a coincidence of position.
    """
    import pandas as pd

    series = wam.copy()
    series["period"] = pd.PeriodIndex(
        pd.to_datetime(series["observation_date"]), freq="M"
    ).astype(str)
    ours = dict(zip(series["period"], series["wam_years"]))

    out = []
    for hit in stated:
        period = hit.get("document_date")
        if not period or period not in ours:
            out.append({**{k: hit[k] for k in ("value", "unit", "population")},
                        "document_date": period,
                        "comparable": False,
                        "why": ("no date read from the document" if not period
                                else f"our series has no {period}")})
            continue
        stated_months = hit["value"] * (12 if hit["unit"] == "year" else 1)
        our_months = ours[period] * 12
        out.append({
            "document_date": period,
            "stated": hit["value"], "stated_unit": hit["unit"],
            "stated_months": round(stated_months, 1),
            "our_months": round(our_months, 1),
            "difference_months": round(stated_months - our_months, 1),
            "population": hit["population"],
            "comparable": True,
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--budget-seconds", type=float, default=600)
    parser.add_argument("--max-bytes", type=int, default=12_000_000)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-indexes", type=int, default=40)
    args = parser.parse_args()

    started = time.monotonic()
    report: dict = {
        "probe": "treasury_published_average_maturity",
        "our_value_years": None,
        "documents": [],
        "evidence": [],
    }

    # State our own number in the report, so the comparison is on one page.
    wam_path = REPO_ROOT / "data" / "processed" / "wam.parquet"
    if wam_path.exists():
        import pandas as pd

        wam = pd.read_parquet(wam_path).sort_values("observation_date")
        report["our_value_years"] = round(float(wam["wam_years"].iloc[-1]), 3)
        report["our_value_months"] = round(report["our_value_years"] * 12, 1)
        report["our_observation"] = str(wam["observation_date"].iloc[-1])[:10]

    candidates: list[dict] = []
    indexes: list[dict] = []
    for url in ENTRY_POINTS:
        record = fetch(url, args.timeout, max_bytes=args.max_bytes)
        payload = record.pop("_payload", None)
        if payload is not None:
            documents, found_indexes = links_from(record.get("final_url", url), payload)
            candidates.extend(documents)
            indexes.extend(found_indexes)
        time.sleep(args.delay)

    # The archive hop. Omitted in the first version of this probe, which then
    # read 16 documents all from one quarter — the identical failure this
    # project already diagnosed and fixed in probe_tbac. Reusing that module's
    # fetching helpers did not carry over its lesson.
    seen = {e["url"] for e in candidates}
    for index in indexes[: args.max_indexes]:
        if time.monotonic() - started > args.budget_seconds * 0.4:
            report["index_expansion_truncated"] = True
            break
        record = fetch(index["url"], args.timeout, max_bytes=args.max_bytes)
        payload = record.pop("_payload", None)
        if payload is not None:
            documents, _ = links_from(record.get("final_url", index["url"]), payload)
            candidates.extend(d for d in documents if d["url"] not in seen)
            seen.update(d["url"] for d in documents)
        time.sleep(args.delay)

    # ODM's own quarterly deck is where the figure is published; the committee's
    # charges and minutes discuss it but Treasury states it.
    ranked = sorted(
        {c["url"]: c for c in candidates}.values(),
        key=lambda c: 0 if re.search(
            r"presentation|treasurypresentation", c["url"] + (c["label"] or ""), re.I
        ) else 1,
    )
    print(f"{len(ranked)} candidate document(s); ODM presentations first", flush=True)

    for position, link in enumerate(ranked):
        if time.monotonic() - started > args.budget_seconds:
            report["stopped_on_budget"] = {
                "after_documents": position,
                "documents_unread": len(ranked) - position,
            }
            print(f"  BUDGET REACHED after {position}; "
                  f"{len(ranked) - position} unread", flush=True)
            break
        record = fetch(link["url"], args.timeout, max_bytes=args.max_bytes)
        text, why_empty = text_of(record)
        record.pop("_payload", None)
        record["label"] = link["label"]
        record["characters_extracted"] = len(text)
        if why_empty:
            record["text_unavailable"] = why_empty
        if text:
            found = find_values(text)
            kept = [h for h in found if not h["rejected"]]
            # Rejections are recorded, as they are in probe_tbac. Without them a
            # zero is unreadable: filters that are correctly conservative and
            # filters that are over-aggressive both produce no values, and the
            # difference decides whether the conclusion is about Treasury's
            # documents or about my regex.
            for hit in found:
                if hit["rejected"]:
                    report.setdefault("rejected_values", []).append({
                        "url": link["url"], "value": hit["value"],
                        "unit": hit["unit"], "why": hit["rejected"],
                        "context": hit["context"][:400],
                    })
            published = document_date(text)
            record["document_date"] = published
            for hit in kept:
                hit["document_date"] = published
            mentions = term_mentions(text)
            record["term_mentions"] = len(mentions)
            if kept:
                report["evidence"].append(
                    {"url": link["url"], "label": link["label"], "hits": kept}
                )
                print(f"  {link['label'][:55]}: {len(kept)} value(s)", flush=True)
            elif mentions:
                # The diagnostic case: the document DOES discuss average maturity
                # and no value was extracted next to it. Either it is stated in a
                # shape the pattern misses, or it is only in a chart. Recorded
                # verbatim so the next iteration is informed rather than guessed.
                report.setdefault("term_without_value", []).append(
                    {"url": link["url"], "label": link["label"], "samples": mentions}
                )
                print(f"  {link['label'][:55]}: term appears {len(mentions)}x, "
                      f"no value matched", flush=True)
        report["documents"].append(record)
        time.sleep(args.delay)

    values = [h for e in report["evidence"] for h in e["hits"]]
    report["documents_with_text"] = sum(
        1 for d in report["documents"] if d.get("characters_extracted")
    )
    if not report["documents_with_text"]:
        report["outcome"] = "NOT REACHED"
    elif values:
        report["outcome"] = "VALUES FOUND"
    else:
        report["outcome"] = "NOT FOUND"
    if report.get("stopped_on_budget") and report["outcome"] == "NOT FOUND":
        report["outcome"] = "NOT FOUND (PARTIAL)"

    # BEFORE the write. This block sat after it, so the reconciliation was
    # computed, printed to stdout, and never persisted — the committed evidence
    # had no comparison in it at all.
    if values and wam_path.exists():
        import pandas as pd

        comparisons = reconcile(values, pd.read_parquet(wam_path))
        report["reconciliation"] = comparisons
        report["comparable_values"] = sum(1 for c in comparisons if c["comparable"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "wam_reference.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(f"\n{report['outcome']}: {len(values)} stated value(s) across "
          f"{len(report['evidence'])} document(s)")
    if report.get("our_value_years"):
        print(f"ours: {report['our_value_years']}y "
              f"({report['our_value_months']} months) at {report['our_observation']}")
    if report.get("reconciliation"):
        comparisons = report["reconciliation"]
        usable = [c for c in comparisons if c["comparable"]]
        print(f"\n{len(usable)} of {len(comparisons)} stated value(s) could be "
              f"dated and matched to our series")
        for c in usable[:15]:
            print(f"  {c['document_date']}: Treasury {c['stated']} "
                  f"{c['stated_unit']}(s) = {c['stated_months']}mo | "
                  f"ours {c['our_months']}mo | diff {c['difference_months']:+.1f}mo "
                  f"| {c['population']}")
        if usable:
            worst = max(usable, key=lambda c: abs(c["difference_months"]))
            print(f"  largest gap: {worst['difference_months']:+.1f} months "
                  f"at {worst['document_date']}")
    for hit in values[:12]:
        print(f"  {hit['value']} {hit['unit']}(s) — {hit['population']}")
    rejected = report.get("rejected_values") or []
    if rejected:
        from collections import Counter

        print(f"\n{len(rejected)} value(s) rejected:")
        for why, count in Counter(r["why"] for r in rejected).most_common():
            print(f"  {count:>3}  {why}")
    for item in (report.get("term_without_value") or [])[:6]:
        print(f"\n  TERM WITHOUT VALUE — {item['label'][:60]}")
        for sample in item["samples"][:2]:
            print(f"    ...{sample[:260]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
