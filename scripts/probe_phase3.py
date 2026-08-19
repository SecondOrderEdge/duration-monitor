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
            # /dataflow/OECD 404s; the unqualified listing works but is 8.9MB.
            "https://sdmx.oecd.org/public/rest/dataflow/OECD.GOV.GSD?format=sdmx-json",
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
            # Securities issues, euro area government, one series, one observation:
            # enough to expose the dimension structure without pulling 18MB.
            "https://data-api.ecb.europa.eu/service/data/SEC/Q.I9.1000.F33000.N.I.Z01.A?lastNObservations=1&format=jsondata",
            "https://data-api.ecb.europa.eu/service/data/SEC?lastNObservations=1&format=jsondata&detail=serieskeysonly",
            "https://data-api.ecb.europa.eu/service/datastructure/ECB/ECB_SEC1?format=sdmx-json",
        ],
    },
    "eurostat": {
        "publisher": "Eurostat",
        "why": "Government debt by instrument and maturity (gov_10q_ggdebt), "
               "quarterly, harmonised across member states.",
        "would_feed": "bill share, debt composition",
        "urls": [
            # One country, one quarter. The dimension block is the same size
            # whatever the filter, and it is the part that decides whether bill
            # share and a maturity split are computable at all.
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10q_ggdebt?format=JSON&lang=EN&geo=DE&time=2025-Q4",
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/gov_10q_ggdebt?format=JSON&lang=EN&geo=IT&time=2025-Q4",
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


# Coverage probes. The point-in-time percentiles need 60 months of history before
# the score publishes at all, so how far back each country's series reaches
# decides feasibility before any design question matters.
#
# The key order is the dimension order the structure probe returned:
#   FREQ.REF_AREA.SEC_ISSUING_SECTOR.SEC_ITEM.SEC_VALUATION
#   .DATA_TYPE_SEC.CURRENCY_TRANS.SERIES_DENOM.SEC_SUFFIX
# Trailing positions are left empty, which SDMX reads as a wildcard — a
# constructed full key returned 400 on the previous run, and guessing the tail is
# how that happened.
ECB_COVERAGE = {
    f"{country}_{label}": f"M.{country}.S131.{item}.N.{data_type}...."
    for country in ("DE", "FR", "IT")
    for label, item, data_type in (
        ("shortterm_stock", "F33100", "1"),
        ("longterm_stock", "F33200", "1"),
        ("shortterm_netissues", "F33100", "4"),
    )
}
ECB_DATA_URL = "https://data-api.ecb.europa.eu/service/data/SEC/{key}"


def observation_period(parsed: dict) -> str | None:
    """The TIME_PERIOD carried on an SDMX-JSON response's observation axis."""
    dims = ((parsed.get("structure") or {}).get("dimensions") or {}).get("observation")
    for dim in dims or []:
        if dim.get("id") == "TIME_PERIOD":
            values = dim.get("values") or []
            if values:
                return values[0].get("id")
    return None


def probe_ecb_coverage(timeout: int) -> dict:
    """First and last observation of each candidate ECB series.

    Two one-observation requests rather than a full history: the coverage bounds
    are all that is being asked, and pulling twenty years of monthly data to read
    two dates would be rude to a public API.
    """
    results: dict = {}
    for name, key in ECB_COVERAGE.items():
        entry: dict = {"key": key}
        for end, param in (("first", "firstNObservations"), ("last", "lastNObservations")):
            url = ECB_DATA_URL.format(key=key) + f"?{param}=1&format=jsondata"
            try:
                response = requests.get(url, timeout=timeout)
                if not response.ok:
                    entry[end] = f"HTTP {response.status_code}"
                    continue
                parsed = response.json()
                entry[end] = observation_period(parsed) or "no observation returned"
                if end == "first":
                    series = (parsed.get("dataSets") or [{}])[0].get("series") or {}
                    entry["n_series_matched"] = len(series)
            except Exception as exc:  # noqa: BLE001
                entry[end] = f"{type(exc).__name__}: {exc}"
        results[name] = entry
    return results


def describe_dimensions(parsed: dict) -> dict | None:
    """Name the axes of an SDMX-JSON or JSON-stat response and their categories.

    This is the part that decides what Phase 3 can compute. A response is only
    useful here if it splits government debt by MATURITY — without that there is
    no bill share, and without per-security detail there is no WAM. Reading the
    numbers tells you nothing about that; reading the dimensions tells you
    everything, so they are recorded in full while the values are not.
    """
    out: dict = {}

    # JSON-stat (Eurostat): dimension ids with a category label map each.
    if isinstance(parsed.get("dimension"), dict):
        for name, spec in parsed["dimension"].items():
            if not isinstance(spec, dict):
                continue
            labels = ((spec.get("category") or {}).get("label")) or {}
            out[name] = {
                "label": spec.get("label"),
                "n_categories": len(labels),
                "categories": dict(list(labels.items())[:20]),
            }
        return out or None

    # SDMX-JSON: structure.dimensions.series / .observation
    structure = parsed.get("structure")
    if isinstance(structure, dict):
        groups = structure.get("dimensions") or {}
        for where in ("series", "observation"):
            for dim in groups.get(where, []) or []:
                values = dim.get("values") or []
                out[f"{where}:{dim.get('id')}"] = {
                    "label": dim.get("name"),
                    "n_categories": len(values),
                    "categories": {
                        v.get("id"): v.get("name") for v in values[:20]
                    },
                }
        return out or None
    return None


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
                dims = describe_dimensions(parsed)
                if dims:
                    entry["dimensions"] = dims
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

    if "ecb" in wanted:
        print("probing ECB coverage depth ...", flush=True)
        report["ecb_coverage"] = probe_ecb_coverage(args.timeout)

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

    coverage = report.get("ecb_coverage")
    if coverage:
        lines += [
            "## ECB coverage depth",
            "",
            "How far back each candidate series reaches. The point-in-time "
            "percentiles need 60 months before the score publishes at all, so "
            "this decides feasibility before any design question does.",
            "",
            "| series | first | last | series matched |",
            "|---|---|---|---|",
        ]
        for name, entry in coverage.items():
            lines.append(
                f"| `{name}` | {entry.get('first')} | {entry.get('last')} | "
                f"{entry.get('n_series_matched', '-')} |"
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
                for dim, spec in (result.get("dimensions") or {}).items():
                    cats = ", ".join(
                        f"`{k}`={v}" for k, v in list(spec["categories"].items())[:8]
                    )
                    lines.append(
                        f"- **{dim}** ({spec['label']}) — {spec['n_categories']} "
                        f"categories: {cats}"
                    )
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
