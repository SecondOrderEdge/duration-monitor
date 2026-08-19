#!/usr/bin/env python3
"""Discover what Phase 3 sovereign data is actually available, and in what shape.

Phase 1 began by assuming field names and having a probe correct them; that probe
found a CUSIP field that does not exist, a TIPS rename, and a table whose totals
include matured securities. Phase 3 covers five more sovereigns and five more
publishers, so it starts the same way: find out what the sources return before
designing anything that consumes them.

This is DISCOVERY, not a contract check. `probe_sources.py` verifies declared
field names against live responses; nothing is declared yet here, so this records
what each candidate returns and leaves the judgement to a human reading it.

It has to run somewhere with open egress. Every host below is refused by this
development environment's network policy (403 at CONNECT), while the Phase 1
hosts are permitted — so it runs in GitHub Actions, the same way FRED does.

Usage:
    python scripts/probe_phase3.py
    python scripts/probe_phase3.py --only ecb --timeout 60
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import traceback

import requests

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TIMEOUT_DEFAULT = 45
SAMPLE_BYTES = 1500

# Candidate sources. Each entry states WHY it is a candidate and what Phase 1
# calculation it would have to feed, so a probe result can be judged against a
# purpose rather than just recorded as reachable.
CANDIDATES: dict[str, dict] = {
    "bis": {
        "publisher": "Bank for International Settlements",
        "why": "Debt securities statistics by residence, sector and maturity. "
               "The brief names it first for cross-sovereign comparability.",
        "would_feed": "bill share, maturity composition",
        "urls": [
            "https://stats.bis.org/api/v1/dataflow/BIS",
            "https://stats.bis.org/api/v1/dataflow",
            "https://www.bis.org/statistics/index.htm",
        ],
    },
    "oecd": {
        "publisher": "OECD",
        "why": "Central government debt statistics, including maturity structure "
               "on a harmonised basis across members.",
        "would_feed": "WAM proxy, maturity buckets",
        "urls": [
            "https://sdmx.oecd.org/public/rest/dataflow/OECD",
            "https://sdmx.oecd.org/public/rest/dataflow",
        ],
    },
    "ecb": {
        "publisher": "European Central Bank",
        "why": "Securities issues statistics and government finance statistics "
               "cover Germany, France and Italy on one basis, which is three of "
               "the five Phase 3 sovereigns from a single publisher.",
        "would_feed": "bill share, net issuance, term premium inputs",
        "urls": [
            "https://data-api.ecb.europa.eu/service/dataflow/ECB",
            "https://data-api.ecb.europa.eu/service/data/SEC?lastNObservations=1&format=jsondata",
        ],
    },
    "eurostat": {
        "publisher": "Eurostat",
        "why": "Government debt by instrument and maturity (gov_10q_ggdebt), "
               "quarterly, harmonised across member states.",
        "would_feed": "bill share, debt composition",
        "urls": [
            "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT",
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10q_ggdebt?format=JSON&lang=EN",
        ],
    },
    "uk_dmo": {
        "publisher": "UK Debt Management Office",
        "why": "Gilt and Treasury bill issuance, per-security detail. The UK is "
               "the closest analogue to the US data estate.",
        "would_feed": "bill share, WAM, auction stress",
        "urls": [
            "https://www.dmo.gov.uk",
            "https://www.dmo.gov.uk/data/",
        ],
    },
    "japan_mof": {
        "publisher": "Japan Ministry of Finance",
        "why": "JGB issuance and outstanding by maturity. Japan is the largest "
               "test of the thesis outside the US.",
        "would_feed": "bill share, WAM",
        "urls": [
            "https://www.mof.go.jp/english/policy/jgbs/index.html",
            "https://www.mof.go.jp",
        ],
    },
    "germany_finanzagentur": {
        "publisher": "Deutsche Finanzagentur",
        "why": "Bund issuance calendar and outstanding securities.",
        "would_feed": "bill share, auction stress",
        "urls": ["https://www.deutsche-finanzagentur.de/en/"],
    },
    "france_aft": {
        "publisher": "Agence France Trésor",
        "why": "OAT and BTF issuance and outstanding.",
        "would_feed": "bill share, WAM",
        "urls": ["https://www.aft.gouv.fr/en"],
    },
    "italy_mef": {
        "publisher": "Italian Treasury (MEF)",
        "why": "BOT and BTP issuance and outstanding.",
        "would_feed": "bill share, WAM",
        "urls": ["https://www.dt.mef.gov.it/en/debito_pubblico/"],
    },
}


def probe_url(url: str, timeout: int) -> dict:
    """Fetch one candidate URL and record what came back, without interpreting it."""
    entry: dict = {"url": url}
    try:
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        body = response.content
        entry.update({
            "status": "ok" if response.ok else "http_error",
            "status_code": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "content_length_bytes": len(body),
            "final_url": response.url,
        })
        # A sample rather than a parse: the point is to see the shape, and
        # guessing at a parser for nine different publishers would be inventing
        # exactly the assumptions this script exists to avoid.
        text = body[:SAMPLE_BYTES].decode("utf-8", errors="replace")
        entry["sample"] = text
        if "json" in (entry["content_type"] or "").lower():
            try:
                parsed = response.json()
                entry["json_top_level_keys"] = (
                    sorted(parsed)[:25] if isinstance(parsed, dict) else f"list[{len(parsed)}]"
                )
            except ValueError:
                entry["json_parse_failed"] = True
    except Exception as exc:  # noqa: BLE001 - a probe reports failures, never raises
        message = f"{type(exc).__name__}: {exc}"
        entry.update({"status": "error", "error": message})
        # A CONNECT refusal is an egress policy denial, not a dead source. Saying
        # which is the difference between "this publisher is unusable" and "this
        # job ran in the wrong place".
        if "CONNECT tunnel failed" in message or "403" in message:
            entry["likely_cause"] = "network egress policy denial, not source failure"
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=sorted(CANDIDATES), action="append")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT)
    args = parser.parse_args()

    wanted = args.only or sorted(CANDIDATES)
    stamp = dt.datetime.now(dt.timezone.utc)
    outdir = REPO_ROOT / "docs" / "source_probe" / "phase3" / stamp.strftime("%Y-%m-%d")
    outdir.mkdir(parents=True, exist_ok=True)

    report: dict = {"probe_timestamp_utc": stamp.isoformat(), "sources": {}}

    for name in wanted:
        spec = CANDIDATES[name]
        print(f"probing {name} ({spec['publisher']}) ...", flush=True)
        results = [probe_url(url, args.timeout) for url in spec["urls"]]
        report["sources"][name] = {
            "publisher": spec["publisher"],
            "why": spec["why"],
            "would_feed": spec["would_feed"],
            "results": results,
            "any_reachable": any(r.get("status") == "ok" for r in results),
        }

    (outdir / "probe.json").write_text(json.dumps(report, indent=2, default=str),
                                       encoding="utf-8")
    write_markdown(report, outdir / "README.md")

    reachable = [n for n, s in report["sources"].items() if s["any_reachable"]]
    blocked = [n for n, s in report["sources"].items() if not s["any_reachable"]]

    print(f"\nEvidence written to {outdir.relative_to(REPO_ROOT)}/")
    print(f"\nreachable: {reachable or 'none'}")
    print(f"unreachable: {blocked or 'none'}")
    print(
        "\nThis is discovery, not a contract. Nothing here is verified until a "
        "field list is declared in config/ and checked against a live response."
    )
    # Discovery does not fail a build: an unreachable candidate is a finding.
    return 0


def write_markdown(report: dict, path: pathlib.Path) -> None:
    lines = [
        "# Phase 3 source discovery",
        "",
        f"- Probe run (UTC): `{report['probe_timestamp_utc']}`",
        "",
        "What each candidate publisher actually returns. This is DISCOVERY — no "
        "field names are declared yet, so nothing here is verified. It exists so "
        "the Phase 3 schema is designed against observed responses rather than "
        "assumptions, which is what the Phase 1 probe was for.",
        "",
        "| source | publisher | reachable | would feed |",
        "|---|---|---|---|",
    ]
    for name, source in report["sources"].items():
        mark = "yes" if source["any_reachable"] else "**no**"
        lines.append(
            f"| `{name}` | {source['publisher']} | {mark} | {source['would_feed']} |"
        )
    lines.append("")

    for name, source in report["sources"].items():
        lines += [f"## `{name}` — {source['publisher']}", "", source["why"], ""]
        for result in source["results"]:
            lines.append(f"### `{result['url']}`")
            lines.append("")
            if result.get("status") == "ok":
                lines += [
                    f"- HTTP {result['status_code']}, "
                    f"`{result.get('content_type')}`, "
                    f"{result.get('content_length_bytes'):,} bytes",
                ]
                if result.get("final_url") != result["url"]:
                    lines.append(f"- redirected to `{result.get('final_url')}`")
                if result.get("json_top_level_keys"):
                    lines.append(f"- JSON top-level keys: `{result['json_top_level_keys']}`")
                lines += ["", "```", result.get("sample", "")[:1200], "```", ""]
            else:
                lines += [f"- **{result.get('status')}**: `{result.get('error', result.get('status_code'))}`"]
                if result.get("likely_cause"):
                    lines.append(f"- {result['likely_cause']}")
                lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
