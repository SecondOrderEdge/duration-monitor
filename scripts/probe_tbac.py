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

# Ranges stated as percentages, in either order relative to the word "bill".
# Deliberately loose: a narrow pattern that found nothing would be indistinguishable
# from an absent claim.
# Separators seen in real prose. "and" is included because "between 20 and 25
# percent" is ordinary English and a pattern that accepted only dashes and "to"
# would have reported the claim absent when it was merely phrased differently —
# a false NOT FOUND is the most damaging output this probe can produce.
_SEP = r"(?:to|and|-|–|—)"
_RANGE = rf"(\d{{1,2}})\s*(?:%|percent)?\s*{_SEP}\s*(\d{{1,2}})\s*(?:%|percent)"
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


def fetch(url: str, timeout: int) -> dict:
    record: dict = {"url": url, "fetched": False}
    try:
        response = requests.get(
            url, timeout=timeout, headers={"User-Agent": UA}, allow_redirects=True
        )
        record["status"] = response.status_code
        record["final_url"] = response.url
        record["content_type"] = response.headers.get("content-type", "")
        response.raise_for_status()
        record["fetched"] = True
        record["_payload"] = response.content
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def text_of(record: dict) -> tuple[str, str | None]:
    payload = record.get("_payload")
    if payload is None:
        return "", record.get("error", "not fetched")
    kind = (record.get("content_type") or "").lower()
    if "pdf" in kind or record["url"].lower().endswith(".pdf"):
        return extract_pdf(payload)
    try:
        return clean_html(payload.decode("utf-8", errors="replace")), None
    except Exception as exc:  # noqa: BLE001
        return "", f"{type(exc).__name__}: {exc}"


def links_from(base_url: str, raw: bytes) -> list[dict]:
    out, seen = [], set()
    page = raw.decode("utf-8", errors="replace")
    for match in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.I | re.S):
        href, label = match.group(1), clean_html(match.group(2))
        absolute = urllib.parse.urljoin(base_url, href)
        if absolute in seen or not absolute.startswith("http"):
            continue
        if not (TBAC_HINTS.search(label) or TBAC_HINTS.search(absolute)):
            continue
        seen.add(absolute)
        out.append({"url": absolute, "label": label[:160]})
    return out


def find_claims(text: str, *, window: int = 320) -> list[dict]:
    """Every stated percentage range near the word 'bill', with context. Unjudged."""
    hits = []
    for match in RANGE_NEAR_BILL.finditer(text):
        groups = [g for g in match.groups() if g is not None]
        start = max(match.start() - window, 0)
        hits.append({
            "range": [int(groups[0]), int(groups[1])] if len(groups) >= 2 else None,
            "matches_configured_band": (
                len(groups) >= 2 and {int(groups[0]), int(groups[1])} == {15, 20}
            ),
            "context": text[start:match.end() + window].strip(),
        })
        if len(hits) >= 25:
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
        "found no stated percentage range near a mention of bills."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--max-documents", type=int, default=40)
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds between requests; this is someone else's server")
    args = parser.parse_args()

    report: dict = {
        "probe": "tbac_bill_share_band",
        "claim_under_test": "reference_levels.bill_share_recommended_band == [0.15, 0.20]",
        "entry_points": [],
        "documents": [],
        "evidence": [],
    }

    candidates: list[dict] = []
    for url in ENTRY_POINTS:
        record = fetch(url, args.timeout)
        payload = record.pop("_payload", None)
        found = []
        if payload is not None:
            found = links_from(record.get("final_url", url), payload)
            candidates.extend(found)
        record["links_found"] = len(found)
        report["entry_points"].append(record)
        print(f"  {url}\n    {'ok' if record['fetched'] else record.get('error')}"
              f" — {len(found)} candidate link(s)", flush=True)
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
    ordered = ordered[: args.max_documents]
    print(f"\n{len(ordered)} candidate document(s) after de-duplication "
          f"(cap {args.max_documents})")
    if len(candidates) > len(ordered):
        # Never let a cap masquerade as full coverage.
        print(f"  NOTE: {len(seen) - len(ordered)} discovered document(s) NOT "
              f"examined because of --max-documents")
        report["documents_skipped_by_cap"] = len(seen) - len(ordered)

    extracted = 0
    for link in ordered:
        record = fetch(link["url"], args.timeout)
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
            if hits:
                report["evidence"].append({"url": link["url"], "label": link["label"],
                                           "hits": hits})
        report["documents"].append(record)
        status = (f"{len(text):,} chars" if text else f"NO TEXT — {why_empty}")
        print(f"  {link['label'][:70] or link['url'][-60:]}: {status}", flush=True)
        time.sleep(args.delay)

    report["documents_with_text"] = extracted
    report["documents_examined"] = len(ordered)
    report["outcome"], report["detail"] = classify_outcome(extracted, report["evidence"])

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
        "## Entry points", "",
        "| url | fetched | status | candidate links |", "|---|---|---|---|",
    ]
    for entry in report["entry_points"]:
        lines.append(
            f"| `{entry['url'][:80]}` | {'yes' if entry['fetched'] else 'no'} | "
            f"{entry.get('status', entry.get('error', ''))} | {entry.get('links_found', 0)} |"
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
