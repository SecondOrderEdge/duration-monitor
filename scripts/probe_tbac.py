"""Find the TBAC document behind the 15-20% bill share band, or fail to.

`reference_levels.bill_share_recommended_band` is the one number on the dashboard
sourced to memory rather than to a fetched artefact. It is shown as a shaded band
on the bill share chart and used in no calculation, so the exposure is
presentational — but "TBAC recommends 15-20%" is a claim about what a committee
wrote, and only the committee's own document can confirm it.

Two failure modes this probe is built to tell apart, because they look identical
in a summary and mean opposite things:

  NOT FOUND   — searched the published record and no such statement turned up.
                That is evidence the paraphrase is wrong, or that the guidance
                lives somewhere this probe did not look.
  NOT REACHED — the host refused, the archive moved, the PDFs would not parse.
                That is evidence about the probe, not about TBAC.

So every document is recorded with whether it was fetched, whether its text was
extracted, and how many characters came out. A zero-hit report over documents
that never yielded text is not a finding.

Matches are returned with surrounding context and NOT auto-classified. Whether a
sentence is a recommendation, an observation of where the share currently sits,
or a scenario in a slide deck is a reading question, and a regex that decided it
would be inventing the answer this probe exists to find.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import pathlib
import re
import sys
import time
import urllib.parse

import requests

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

OUT_DIR = REPO_ROOT / "docs" / "source_probe" / "tbac"

# Treasury moved the refunding material at least once, so several entry points
# are tried and each records its own outcome. One 404 is a moved page, not a
# blocked host, and the two must not be reported as the same thing.
ENTRY_POINTS = [
    "https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding",
    "https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/quarterly-refunding-archives",
    "https://home.treasury.gov/policy-issues/financing-the-government/treasury-borrowing-advisory-committee",
    "https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/most-recent-quarterly-refunding-documents",
]

UA = "duration-monitor source probe (+https://github.com/SecondOrderEdge/duration-monitor)"

# Link text or href that suggests a TBAC document rather than a data release.
TBAC_HINTS = re.compile(
    r"tbac|borrowing[- ]advisory|refunding[- ]document|report[- ]to[- ]the[- ]secretary"
    r"|minutes|charge",
    re.I,
)

# The first run searched 17 documents and every one was Q3 2026, because the
# filter above demands a TBAC-ish WORD and the archive lists quarters by DATE —
# "2015 - 2nd Quarter", "August 2011". Those links were dropped, coverage
# collapsed to the current quarter, and a NOT FOUND over one quarter cannot
# speak to a claim about what the committee has "long referenced".
DATED_LINK = re.compile(r"(?:19|20)\d{2}|\b(?:1st|2nd|3rd|4th)\s+quarter\b", re.I)

# Pages worth opening for MORE links rather than searching for text.
INDEX_HINTS = re.compile(r"archive|quarterly-refunding|refunding-documents", re.I)

# Anything under /system/files/ or ending .pdf is the artefact itself; press
# releases carry the minutes and the report to the Secretary as HTML.
DOCUMENT_HINTS = re.compile(r"/system/files/|\.pdf$|/news/press-releases/", re.I)

YEAR = re.compile(r"(?:19|20)\d{2}")

# Ranges stated as percentages, in either order relative to the word "bill".
# Deliberately loose: a narrow pattern that found nothing would be indistinguishable
# from an absent claim.
# Separators seen in real prose. "and" is included because "between 20 and 25
# percent" is ordinary English and a pattern that accepted only dashes and "to"
# would have reported the claim absent when it was merely phrased differently —
# a false NOT FOUND is the most damaging output this probe can produce.
_SEP = r"(?:to|and|-|–|—)"
# \b matters more than it looks. Without it, `\d{1,2}` matches INSIDE a longer
# number: "December 2008 to 70%" yielded the range [8, 70] in a live run, pairing
# the tail of a year with a percentage and reporting it as a stated range.
_RANGE = (
    rf"\b(\d{{1,2}})\b\s*(?:%|percent)?\s*{_SEP}\s*\b(\d{{1,2}})\b\s*(?:%|percent)"
)
RANGE_NEAR_BILL = re.compile(
    rf"(?:bill|t-bill|treasury bill)[^.]{{0,250}}?{_RANGE}"
    rf"|{_RANGE}[^.]{{0,250}}?(?:bill|t-bill|treasury bill)",
    re.I | re.S,
)
BILL_SHARE_PHRASE = re.compile(
    r"(?:bill|t-bill)[a-z ]{0,20}(?:share|as a (?:percent|share)|percentage)"
    r"|(?:share|percentage) of (?:marketable )?(?:debt|portfolio)[^.]{0,60}bill",
    re.I | re.S,
)


# Document classes, in the order they are worth reading. The claim under test is
# a sentence — "the Committee recommends..." — so it lives in the minutes or the
# report to the Secretary, not in a chart deck. The first full run spent its
# entire budget with 50 of 73 documents being chart decks and read no minutes at
# all, which is how a search can be large and still miss the only place the
# answer could be.
DOCUMENT_CLASSES = [
    ("minutes", re.compile(r"minutes", re.I)),
    ("report", re.compile(r"report[- ]to[- ]the[- ]secretary|report", re.I)),
    ("press release", re.compile(r"/news/press-releases/", re.I)),
    ("charge", re.compile(r"charge", re.I)),
    ("chart deck", re.compile(r"chart|template|presentation", re.I)),
]


def classify_document(entry: dict) -> str:
    haystack = f"{entry['url']} {entry.get('label') or ''}"
    for name, pattern in DOCUMENT_CLASSES:
        if pattern.search(haystack):
            return name
    return "other"


def read_order(entry: dict) -> int:
    """Sort key: prose before charts, so a truncated run truncates the right end."""
    name = classify_document(entry)
    order = {n: i for i, (n, _) in enumerate(DOCUMENT_CLASSES)}
    return order.get(name, len(DOCUMENT_CLASSES) - 1)


def clean_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def extract_pdf(payload: bytes) -> tuple[str, str | None]:
    """PDF text, plus why it is empty when it is."""
    try:
        import pypdf
    except ImportError:
        return "", "pypdf not installed; run `pip install -r requirements-probe.txt`"
    try:
        reader = pypdf.PdfReader(io.BytesIO(payload))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        return "", f"{type(exc).__name__}: {exc}"
    text = re.sub(r"\s+", " ", " ".join(pages)).strip()
    if not text:
        # A scanned report yields zero characters and no error at all, which
        # would otherwise be filed as "searched, found nothing".
        return "", "no extractable text (likely a scanned image PDF)"
    return text, None


def fetch(url: str, timeout: int, *, max_bytes: int = 0) -> dict:
    """Fetch one URL, refusing anything over `max_bytes`.

    The size cap exists because the combined-charges archives run to tens of
    megabytes and pypdf spends minutes on them. A skipped oversize document is
    recorded as skipped — it still counts against coverage, and pretending
    otherwise would be the same error as counting an unsearched document as
    searched.
    """
    record: dict = {"url": url, "fetched": False}
    try:
        response = requests.get(
            url, timeout=timeout, headers={"User-Agent": UA},
            allow_redirects=True, stream=bool(max_bytes),
        )
        record["status"] = response.status_code
        record["final_url"] = response.url
        record["content_type"] = response.headers.get("content-type", "")
        response.raise_for_status()

        if max_bytes:
            declared = int(response.headers.get("content-length") or 0)
            if declared > max_bytes:
                record["skipped"] = f"{declared:,} bytes exceeds the {max_bytes:,} cap"
                response.close()
                return record
            chunks, total = [], 0
            for chunk in response.iter_content(65536):
                chunks.append(chunk)
                total += len(chunk)
                if total > max_bytes:
                    # Servers do not always declare a length, so the stream is
                    # capped as well as the header.
                    record["skipped"] = f"exceeded the {max_bytes:,} byte cap while reading"
                    response.close()
                    return record
            payload = b"".join(chunks)
        else:
            payload = response.content

        record["fetched"] = True
        record["_payload"] = payload
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def text_of(record: dict) -> tuple[str, str | None]:
    payload = record.get("_payload")
    if payload is None:
        return "", record.get("skipped") or record.get("error", "not fetched")
    kind = (record.get("content_type") or "").lower()
    if "pdf" in kind or record["url"].lower().endswith(".pdf"):
        return extract_pdf(payload)
    try:
        return clean_html(payload.decode("utf-8", errors="replace")), None
    except Exception as exc:  # noqa: BLE001
        return "", f"{type(exc).__name__}: {exc}"


def links_from(base_url: str, raw: bytes) -> tuple[list[dict], list[dict]]:
    """Split a page's links into documents to search and indexes to expand.

    Returns (documents, indexes). A link qualifies as a document if it names a
    TBAC artefact OR carries a date — the second test is what reaches the
    per-quarter archive, which labels its entries by date and not by committee.
    """
    documents, indexes, seen = [], [], set()
    page = raw.decode("utf-8", errors="replace")
    host = urllib.parse.urlparse(base_url).netloc
    for match in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.I | re.S):
        href, label = match.group(1), clean_html(match.group(2))
        absolute = urllib.parse.urljoin(base_url, href).split("#")[0]
        if absolute in seen or not absolute.startswith("http"):
            continue
        # Stay on Treasury's own site; an offsite link is not TBAC's word.
        if urllib.parse.urlparse(absolute).netloc != host:
            continue
        seen.add(absolute)
        entry = {"url": absolute, "label": label[:160]}
        named = TBAC_HINTS.search(label) or TBAC_HINTS.search(absolute)
        dated = DATED_LINK.search(label) or DATED_LINK.search(absolute)
        if DOCUMENT_HINTS.search(absolute) and (named or dated):
            documents.append(entry)
        elif INDEX_HINTS.search(absolute) and (named or dated):
            indexes.append(entry)
    return documents, indexes


def year_of(entry: dict) -> str | None:
    """Best guess at which year a document belongs to, for coverage reporting.

    Guessed, not authoritative — it reads the label and URL. Coverage stated from
    a guess is still far better than coverage left unstated, which is how the
    first run reported seventeen documents without revealing they were all one
    quarter.
    """
    for text in (entry.get("label") or "", entry["url"]):
        years = YEAR.findall(text)
        if years:
            return max(years)
    return None


def looks_like_chart_axis(context: str) -> bool:
    """Whether a match came out of a chart's tick labels rather than a sentence.

    TBAC materials are largely chart decks, and PDF extraction turns an axis into
    a run of bare numbers — "-25 -20 -15 -10 -5", "30 20 10 0". Adjacent numbers
    in that soup look exactly like a stated range. The first bounded run returned
    six "ranges" and every one was axis noise, which produced a confident verdict
    about language nobody had written.

    The test is density: prose about a range is mostly words.
    """
    if not context:
        return False
    digits = sum(character.isdigit() for character in context)
    letters = sum(character.isalpha() for character in context)
    return digits > 0.18 * len(context) or letters < 2 * digits


def find_claims(text: str, *, window: int = 320) -> list[dict]:
    """Stated percentage ranges near the word 'bill', with context. Unjudged.

    Two filters, both learned from false positives rather than anticipated:
    a range must ASCEND (a descending pair is a chart axis, not a range), and
    its surroundings must read as prose rather than as extracted tick labels.
    Rejected matches are still returned, flagged, so a filter that is too
    aggressive is visible in the evidence instead of silently shrinking it.
    """
    hits = []
    for match in RANGE_NEAR_BILL.finditer(text):
        groups = [g for g in match.groups() if g is not None]
        if len(groups) < 2:
            continue
        low, high = int(groups[0]), int(groups[1])
        start = max(match.start() - window, 0)
        context = text[start:match.end() + window].strip()

        rejected = None
        if high <= low:
            rejected = "descending pair; a range runs upward"
        elif looks_like_chart_axis(context):
            rejected = "surroundings read as chart axis labels, not prose"

        hits.append({
            "range": [low, high],
            "matches_configured_band": {low, high} == {15, 20} and rejected is None,
            "rejected": rejected,
            "context": context,
        })
        if len(hits) >= 40:
            break
    return hits


def classify_outcome(documents_with_text: int, evidence: list[dict]) -> tuple[str, str]:
    """Turn counts into a verdict, keeping "searched" and "not searched" apart.

    A separate function because this is the probe's only real judgement, and the
    distinction it encodes — zero hits over zero readable documents is NOT a
    finding about TBAC — is the thing most easily lost when a summary is skimmed.
    """
    exact = [h for e in evidence for h in e["hits"] if h["matches_configured_band"]]
    if documents_with_text == 0:
        return "NOT REACHED", (
            "Documents were located but none yielded text, so nothing was "
            "actually searched. This is a finding about the probe, not about TBAC."
        )
    if exact:
        return "EVIDENCE FOUND", (
            f"{len(exact)} passage(s) state a 15-20% range near a mention of bills. "
            "Read the context before setting verified: a range appearing in a "
            "document is not the same as the committee recommending it."
        )
    if evidence:
        return "OTHER RANGES FOUND", (
            "Ranges near bill mentions were found, but none was 15-20%. If these "
            "are the committee's actual language, the configured band is wrong."
        )
    return "NOT FOUND", (
        f"Searched {documents_with_text} document(s) with extractable text and "
        "found no stated percentage range near a mention of bills. Weigh this "
        "against coverage_by_year: the claim is that TBAC has LONG referenced "
        "the band, so a NOT FOUND spanning few years does not answer it."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--max-documents", type=int, default=400)
    parser.add_argument("--max-indexes", type=int, default=60,
                        help="archive pages to expand for links")
    parser.add_argument("--budget-seconds", type=float, default=900,
                        help="wall-clock ceiling; the probe stops and REPORTS "
                             "what it got rather than running unbounded")
    parser.add_argument("--max-bytes", type=int, default=12_000_000,
                        help="skip documents larger than this")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds between requests; this is someone else's server")
    args = parser.parse_args()

    started = time.monotonic()

    def remaining() -> float:
        return args.budget_seconds - (time.monotonic() - started)

    report: dict = {
        "probe": "tbac_bill_share_band",
        "budget_seconds": args.budget_seconds,
        "claim_under_test": "reference_levels.bill_share_recommended_band == [0.15, 0.20]",
        "entry_points": [],
        "documents": [],
        "evidence": [],
    }

    candidates: list[dict] = []
    indexes: list[dict] = []
    for url in ENTRY_POINTS:
        record = fetch(url, args.timeout, max_bytes=args.max_bytes)
        payload = record.pop("_payload", None)
        found, found_indexes = ([], [])
        if payload is not None:
            found, found_indexes = links_from(record.get("final_url", url), payload)
            candidates.extend(found)
            indexes.extend(found_indexes)
        record["links_found"] = len(found)
        record["indexes_found"] = len(found_indexes)
        report["entry_points"].append(record)
        print(f"  {url}\n    {'ok' if record['fetched'] else record.get('error')}"
              f" — {len(found)} document link(s), {len(found_indexes)} index page(s)",
              flush=True)
        time.sleep(args.delay)

    # Second hop. The archive is a page of pages: the entry points list years and
    # quarters, and the documents hang off those. One level of expansion is what
    # separates "the current quarter" from "the record".
    seen_indexes: set[str] = {e["url"] for e in report["entry_points"]}
    queue = [i for i in indexes if i["url"] not in seen_indexes][: args.max_indexes]
    print(f"\nexpanding {len(queue)} index page(s) (cap {args.max_indexes})")
    report["indexes_expanded"] = []
    for index in queue:
        if index["url"] in seen_indexes:
            continue
        if remaining() <= args.budget_seconds * 0.5:
            # Half the budget is reserved for actually READING documents.
            # A probe that spends all its time discovering links and none
            # searching them has answered nothing.
            report["index_expansion_truncated"] = True
            print("  budget half spent on discovery; stopping expansion", flush=True)
            break
        seen_indexes.add(index["url"])
        record = fetch(index["url"], args.timeout, max_bytes=args.max_bytes)
        payload = record.pop("_payload", None)
        found = []
        if payload is not None:
            found, deeper = links_from(record.get("final_url", index["url"]), payload)
            candidates.extend(found)
            # Deliberately not recursing further. Depth is where a crawl stops
            # being a probe and starts being a mirror of someone else's site.
            for entry in deeper:
                if entry["url"] not in seen_indexes and len(queue) < args.max_indexes:
                    seen_indexes.add(entry["url"])
                    queue.append(entry)
        record["links_found"] = len(found)
        record["label"] = index["label"]
        report["indexes_expanded"].append(record)
        print(f"  {index['label'][:60] or index['url'][-55:]}: "
              f"{len(found) if record['fetched'] else record.get('error')} document link(s)",
              flush=True)
        time.sleep(args.delay)

    if not any(e["fetched"] for e in report["entry_points"]):
        report["outcome"] = "NOT REACHED"
        report["detail"] = (
            "No entry point could be fetched, so nothing was searched. This says "
            "the host is unreachable from here; it says nothing about whether TBAC "
            "states a 15-20% band."
        )
        _write(report)
        print("\nNOT REACHED — no entry point fetched. The claim remains unverified.")
        return 1

    # De-duplicate while keeping discovery order, then cap.
    seen, ordered = set(), []
    for link in candidates:
        if link["url"] not in seen:
            seen.add(link["url"])
            ordered.append(link)
    # Stable sort: prose classes first, discovery order preserved within a class.
    ordered.sort(key=read_order)
    ordered = ordered[: args.max_documents]
    print(f"\n{len(ordered)} candidate document(s) after de-duplication "
          f"(cap {args.max_documents})")
    if len(candidates) > len(ordered):
        # Never let a cap masquerade as full coverage.
        print(f"  NOTE: {len(seen) - len(ordered)} discovered document(s) NOT "
              f"examined because of --max-documents")
        report["documents_skipped_by_cap"] = len(seen) - len(ordered)

    extracted = 0
    for position, link in enumerate(ordered):
        if remaining() <= 0:
            # Stopping early is fine; stopping early and calling it full coverage
            # is not. The count of what went unread is recorded and reported.
            report["stopped_on_budget"] = {
                "after_documents": position,
                "documents_unread": len(ordered) - position,
                "budget_seconds": args.budget_seconds,
            }
            print(f"\n  BUDGET REACHED after {position} document(s); "
                  f"{len(ordered) - position} left unread", flush=True)
            break
        record = fetch(link["url"], args.timeout, max_bytes=args.max_bytes)
        text, why_empty = text_of(record)
        record.pop("_payload", None)
        record["label"] = link["label"]
        record["characters_extracted"] = len(text)
        if why_empty:
            record["text_unavailable"] = why_empty
        if text:
            extracted += 1
            record["mentions_bill_share"] = bool(BILL_SHARE_PHRASE.search(text))
            hits = find_claims(text)
            kept = [h for h in hits if not h["rejected"]]
            if kept:
                report["evidence"].append({"url": link["url"], "label": link["label"],
                                           "hits": kept})
            if len(hits) != len(kept):
                report.setdefault("rejected_matches", []).append({
                    "url": link["url"],
                    "rejected": [{"range": h["range"], "why": h["rejected"]}
                                 for h in hits if h["rejected"]],
                })
        report["documents"].append(record)
        status = (f"{len(text):,} chars" if text else f"NO TEXT — {why_empty}")
        print(f"  {link['label'][:70] or link['url'][-60:]}: {status}", flush=True)
        time.sleep(args.delay)

    report["documents_with_text"] = extracted
    report["documents_examined"] = len(ordered)

    years: dict[str, int] = {}
    for entry, doc in zip(ordered, report["documents"][-len(ordered):]):
        if doc.get("characters_extracted"):
            year = year_of(entry) or "unknown"
            years[year] = years.get(year, 0) + 1
    report["coverage_by_year"] = dict(sorted(years.items()))
    print("\ncoverage of documents that yielded text, by year:")
    print("  " + "  ".join(f"{y}:{n}" for y, n in report["coverage_by_year"].items()))

    # By class as well as by year. A run can cover twenty years and still not
    # have opened a single document of the kind that could carry the claim.
    classes: dict[str, int] = {}
    for entry, doc in zip(ordered, report["documents"][-len(ordered):]):
        if doc.get("characters_extracted"):
            name = classify_document(entry)
            classes[name] = classes.get(name, 0) + 1
    report["coverage_by_class"] = dict(sorted(classes.items()))
    print("by document class:")
    print("  " + "  ".join(f"{k}:{v}" for k, v in report["coverage_by_class"].items()))
    report["outcome"], report["detail"] = classify_outcome(extracted, report["evidence"])
    # Both NOT FOUND and OTHER RANGES FOUND assert the configured band is absent.
    # A run that stopped early cannot assert that, and the first bounded run made
    # exactly this mistake: it reported OTHER RANGES FOUND with 259 documents
    # still unread, which reads as a conclusion and was a progress note.
    if report.get("stopped_on_budget") and report["outcome"] in (
        "NOT FOUND", "OTHER RANGES FOUND"
    ):
        report["outcome"] += " (PARTIAL)"
        report["detail"] += (
            f" The run stopped on its time budget after "
            f"{report['stopped_on_budget']['after_documents']} document(s) with "
            f"{report['stopped_on_budget']['documents_unread']} unread, so it "
            "cannot conclude the band is absent from the record."
        )

    _write(report)
    print(f"\n{report['outcome']}: {report['detail']}")
    return 0


def _write(report: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "tbac_probe.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# TBAC bill share band probe", "",
        f"**Claim under test:** `{report['claim_under_test']}`", "",
        f"**Outcome: {report.get('outcome', 'incomplete')}** — {report.get('detail', '')}",
        "",
        "`NOT FOUND` means the record was searched and the statement is absent.",
        "`NOT REACHED` means the search did not happen. They are not the same finding.",
        "",
    ]
    if report.get("coverage_by_year"):
        lines += [
            "## Coverage", "",
            "Documents that yielded text, by year. **Read the verdict against "
            "this.** The claim is that TBAC has *long* referenced the band, so a "
            "`NOT FOUND` spanning a couple of years does not answer it.", "",
            "| year | documents searched |", "|---|---|",
        ]
        lines += [f"| {year} | {count} |"
                  for year, count in report["coverage_by_year"].items()]
        lines.append("")
        if report.get("coverage_by_class"):
            lines += ["By document class. The claim is a sentence, so the classes "
                      "that matter are minutes and reports; a run heavy in chart "
                      "decks has searched a lot and looked in the wrong place.", "",
                      "| class | documents searched |", "|---|---|"]
            lines += [f"| {name} | {count} |"
                      for name, count in report["coverage_by_class"].items()]
            lines.append("")
    lines += [
        "## Entry points", "",
        "| url | fetched | status | documents | indexes |", "|---|---|---|---|---|",
    ]
    for entry in report["entry_points"]:
        lines.append(
            f"| `{entry['url'][:70]}` | {'yes' if entry['fetched'] else 'no'} | "
            f"{entry.get('status', entry.get('error', ''))} | "
            f"{entry.get('links_found', 0)} | {entry.get('indexes_found', 0)} |"
        )
    if report.get("documents"):
        lines += ["", "## Documents examined", "",
                  "| document | characters | note |", "|---|---|---|"]
        for doc in report["documents"]:
            lines.append(
                f"| {(doc.get('label') or doc['url'])[:70]} | "
                f"{doc.get('characters_extracted', 0):,} | "
                f"{doc.get('text_unavailable', '')} |"
            )
    if report.get("evidence"):
        lines += ["", "## Passages found", ""]
        for item in report["evidence"]:
            lines += [f"### {item['label'] or item['url']}", "", f"<{item['url']}>", ""]
            for hit in item["hits"]:
                mark = " **← matches the configured band**" if hit["matches_configured_band"] else ""
                lines += [f"- range `{hit['range']}`{mark}", "",
                          f"  > {hit['context'][:900]}", ""]
    (OUT_DIR / "tbac_probe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
