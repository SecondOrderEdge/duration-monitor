"""Fetch one quarter's refunding documents and extract the passages a QRA row needs.

The QRA log is manual by design — Phase 1 deliberately does not NLP-extract the
PDFs, and this script does not change that. It does the FETCHING, which the
development environment cannot (home.treasury.gov is refused at CONNECT), and it
extracts VERBATIM passages around the terms a `qra_log.csv` row is built from:
borrowing estimates, the assumed end-of-quarter cash balance, auction size
changes, and the issuance commentary. A human reads the passages and types the
row. No number is parsed into a field by this script, because a mis-parsed
borrowing estimate in a hand-entry log would be worse than an empty one: the log
exists to be the thing that was definitely read off the document.
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
    text_of,
)

OUT_DIR = REPO_ROOT / "docs" / "source_probe" / "qra"

# The terms a QRA row is transcribed from. Each match is returned with wide
# context so the reader gets the sentence Treasury wrote, not a fragment.
TOPICS = {
    "borrowing_estimate": re.compile(
        r"expects to borrow|borrowing estimate|net marketable debt|"
        r"privately-held net marketable", re.I),
    "cash_balance": re.compile(r"cash balance", re.I),
    "auction_sizes": re.compile(
        r"auction size|increase.{0,40}auction|nominal coupon.{0,60}(?:size|increase|maintain)",
        re.I),
    "bills": re.compile(r"\bbill(s)?\b.{0,80}(?:issuance|share|financing)|financing.{0,60}bills", re.I),
    "buybacks": re.compile(r"buyback", re.I),
}


def passages(text: str, pattern: re.Pattern, *, window: int = 450, limit: int = 6) -> list[str]:
    out, last_end = [], -1
    for match in pattern.finditer(text):
        if match.start() < last_end:            # merge overlapping windows
            continue
        start = max(match.start() - window, 0)
        end = match.end() + window
        out.append(" ".join(text[start:end].split()))
        last_end = end
        if len(out) >= limit:
            break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--must-contain", nargs="+", required=True,
                        help="every term must appear in the document label/URL, "
                             "e.g. --must-contain 2023 4th")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--budget-seconds", type=float, default=420)
    parser.add_argument("--max-bytes", type=int, default=12_000_000)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()
    started = time.monotonic()

    terms = [t.lower() for t in args.must_contain]
    report: dict = {"probe": "qra_documents", "target": terms, "documents": []}

    # Every candidate carries the page it was DISCOVERED ON. The archive lists
    # quarters as bare "4th Quarter" links under a year index page, so the year
    # exists only in the parent's URL or label — the first run required every
    # term on the leaf and matched nothing at all.
    candidates, indexes, seen = [], [], set()
    report["entry_points"] = []
    for url in ENTRY_POINTS:
        record = fetch(url, args.timeout, max_bytes=args.max_bytes)
        payload = record.pop("_payload", None)
        docs, idx = [], []
        if payload is not None:
            docs, idx = links_from(record.get("final_url", url), payload)
            for d in docs:
                d["parent"] = url
            candidates += docs
            indexes += idx
        # Recorded and printed, success or not. The first two runs of this
        # script discovered zero documents and gave no way to tell a blocked
        # host from an empty page — the exact opacity every other probe in this
        # repo has had to fix once.
        entry_record = {
            "url": url, "status": record.get("status"),
            "error": record.get("error"), "documents": len(docs), "indexes": len(idx),
        }
        # A 200 with zero links is the one outcome the status line cannot
        # explain: it is either a markup change or a bot-mitigation page served
        # with a success code. Keep enough of the body to tell which.
        if payload is not None and not docs and not idx:
            body = payload.decode("utf-8", errors="replace")
            entry_record["body_sample"] = " ".join(body[:3000].split())
            entry_record["anchor_count"] = body.lower().count("<a ")
        report["entry_points"].append(entry_record)
        print(f"  entry {url[-60:]}: status={record.get('status')} "
              f"docs={len(docs)} indexes={len(idx)}"
              + (f" ERROR {record['error'][:90]}" if record.get("error") else ""),
              flush=True)
        time.sleep(args.delay)
    # The archive is three levels deep: archives -> year page -> quarter page ->
    # documents. A one-level hop reaches the year pages and stops, so the
    # refunding statement and borrowing estimates — which live on the quarter
    # page — were never fetched. Deeper indexes are followed ONLY when they
    # match the target terms ("2023 - 4th Quarter"), so depth stays targeted
    # rather than becoming a site mirror.
    queue = list(indexes[:60])
    crawled = 0
    while queue and crawled < 60:
        index = queue.pop(0)
        if index["url"] in seen or time.monotonic() - started > args.budget_seconds * 0.4:
            continue
        seen.add(index["url"])
        crawled += 1
        record = fetch(index["url"], args.timeout, max_bytes=args.max_bytes)
        payload = record.pop("_payload", None)
        if payload is not None:
            docs, deeper = links_from(record.get("final_url", index["url"]), payload)
            parent_tag = index["url"] + " " + (index["label"] or "")
            for d in docs:
                d["parent"] = parent_tag
            candidates += docs
            for extra in deeper:
                tag = (extra["url"] + " " + (extra["label"] or "") + " "
                       + parent_tag).lower()
                if all(t in tag for t in terms) and extra["url"] not in seen:
                    extra["label"] = (extra["label"] or "") + " | " + (index["label"] or "")
                    queue.append(extra)
                    print(f"  following matching index: {extra['url'][-70:]}", flush=True)
        time.sleep(args.delay)

    unique = list({c["url"]: c for c in candidates}.values())
    def haystack(c):
        return (c["url"] + " " + (c["label"] or "") + " " + c.get("parent", "")).lower()
    matched = [c for c in unique if all(t in haystack(c) for t in terms)]
    print(f"{len(unique)} documents discovered, {len(matched)} match {terms}", flush=True)
    if not matched:
        # A zero must be diagnosable (the lesson every probe here has taught).
        near = [c for c in unique if any(t in haystack(c) for t in terms)]
        print(f"  ZERO matched. {len(near)} documents match at least one term; "
              "first few haystacks:")
        for c in near[:10]:
            print("   ", haystack(c)[:140])
        report["near_misses"] = [haystack(c)[:200] for c in near[:30]]

    for link in matched:
        if time.monotonic() - started > args.budget_seconds:
            report["stopped_on_budget"] = True
            print("  BUDGET REACHED", flush=True)
            break
        record = fetch(link["url"], args.timeout, max_bytes=args.max_bytes)
        text, why = text_of(record)
        record.pop("_payload", None)
        entry = {"url": link["url"], "label": link["label"],
                 "characters": len(text)}
        if why:
            entry["text_unavailable"] = why
        else:
            entry["passages"] = {
                topic: found for topic, pattern in TOPICS.items()
                if (found := passages(text, pattern))
            }
        report["documents"].append(entry)
        print(f"  {link['label'][:60]}: "
              f"{len(entry.get('passages', {}))} topic(s) matched, {len(text):,} chars",
              flush=True)
        time.sleep(args.delay)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = "_".join(terms)
    (OUT_DIR / f"qra_{slug}.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")

    lines = [f"# QRA source passages — {' '.join(terms)}", "",
             "Verbatim extracts for transcribing a `qra_log.csv` row. Read the",
             "passage, type the row, cite the URL. Nothing here is parsed into a",
             "field automatically, and nothing should be.", ""]
    for doc in report["documents"]:
        lines += [f"## {doc['label'] or doc['url']}", "", f"<{doc['url']}>", ""]
        if doc.get("text_unavailable"):
            lines += [f"*no text: {doc['text_unavailable']}*", ""]
        for topic, found in (doc.get("passages") or {}).items():
            lines.append(f"### {topic}")
            lines += [""] + [f"> {p}" for p in found] + [""]
    (OUT_DIR / f"qra_{slug}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n→ docs/source_probe/qra/qra_{slug}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
