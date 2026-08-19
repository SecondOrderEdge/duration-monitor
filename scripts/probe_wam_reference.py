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

OUT_DIR = REPO_ROOT / "docs" / "source_probe" / "wam_reference"

# "average maturity of 71 months", "weighted average maturity was 5.9 years",
# "average length of the marketable debt ... 71 months".
VALUE_NEAR_WAM = re.compile(
    r"(?:weighted[- ]average[- ]maturity|average[- ]maturity|average[- ]length)"
    r"[^.]{0,160}?"
    r"\b(\d{1,3}(?:\.\d{1,2})?)\s*(months?|years?|yrs?)\b"
    r"|\b(\d{1,3}(?:\.\d{1,2})?)\s*(months?|years?|yrs?)\b[^.]{0,160}?"
    r"(?:weighted[- ]average[- ]maturity|average[- ]maturity|average[- ]length)",
    re.I | re.S,
)

# Which population the sentence is about. Left unresolved rather than guessed:
# the distinction decides whether a match is a check or a different measurement.
PRIVATE_INVESTORS = re.compile(r"private investors?|held by the public", re.I)


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

        rejected = None
        if looks_like_chart_axis(context):
            rejected = "surroundings read as chart axis labels, not prose"

        hits.append({
            "value": float(value),
            # Units are RECORDED, never normalised. 71 months and 5.92 years are
            # the same duration, and quietly converting one into the other is how
            # a reader stops noticing which definition they are looking at.
            "unit": "month" if unit.startswith(("month", "mo")) else "year",
            "population": ("private investors" if PRIVATE_INVESTORS.search(context)
                           else "unstated — assume all marketable, but check"),
            "rejected": rejected,
            "context": context,
        })
        if len(hits) >= 40:
            break
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--budget-seconds", type=float, default=600)
    parser.add_argument("--max-bytes", type=int, default=12_000_000)
    parser.add_argument("--delay", type=float, default=1.0)
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
    for url in ENTRY_POINTS:
        record = fetch(url, args.timeout, max_bytes=args.max_bytes)
        payload = record.pop("_payload", None)
        if payload is not None:
            documents, _ = links_from(record.get("final_url", url), payload)
            candidates.extend(documents)
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
            kept = [h for h in find_values(text) if not h["rejected"]]
            if kept:
                report["evidence"].append(
                    {"url": link["url"], "label": link["label"], "hits": kept}
                )
                print(f"  {link['label'][:55]}: {len(kept)} value(s)", flush=True)
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

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "wam_reference.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(f"\n{report['outcome']}: {len(values)} stated value(s) across "
          f"{len(report['evidence'])} document(s)")
    if report.get("our_value_years"):
        print(f"ours: {report['our_value_years']}y "
              f"({report['our_value_months']} months) at {report['our_observation']}")
    for hit in values[:12]:
        print(f"  {hit['value']} {hit['unit']}(s) — {hit['population']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
