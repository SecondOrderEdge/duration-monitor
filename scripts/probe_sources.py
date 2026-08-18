#!/usr/bin/env python3
"""Verify live source field names against the contract in config/sources.yaml.

This exists because field mappings must never be hardcoded from memory. It pulls a
tiny sample from every configured source, records the ACTUAL field names, and
reports them against `expected_fields` as MISSING / UNEXPECTED / OK.

It writes evidence, not data: output goes to docs/source_probe/<UTC date>/, never
to data/. Nothing here is used at runtime by the app.

Usage:
    export FRED_API_KEY=...            # optional; FRED probes skip without it
    python scripts/probe_sources.py            # all sources
    python scripts/probe_sources.py --only fiscaldata
    python scripts/probe_sources.py --timeout 60

Exit code is 0 if every probe succeeded and 1 if any endpoint was unreachable or
broke its contract, so CI can gate on it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import traceback

import requests
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "config" / "sources.yaml"
TIMEOUT_DEFAULT = 45


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

# Credentials must never reach the evidence files. The probe is designed to have
# its output committed, and a failed request stringifies to the full URL —
# api_key included. GitHub Actions masks secrets in job logs but not in files a
# job commits, so masking has to happen here, before anything is written.
#
# The likeliest trigger is exactly what the probe exists to check: an unverified
# series ID that 404s.

_REDACT_TOKENS: set[str] = set()
_API_KEY_RE = re.compile(r"(api_key=)[^&\s\"']+")


def register_secret(value: str | None) -> None:
    """Register a credential to be scrubbed from every recorded string."""
    if value:
        _REDACT_TOKENS.add(value)


def _redact(text: str) -> str:
    """Scrub registered secrets, then any api_key= query parameter."""
    for token in _REDACT_TOKENS:
        text = text.replace(token, "***REDACTED***")
    return _API_KEY_RE.sub(r"\1***REDACTED***", text)


def _get_json(url: str, params: dict, timeout: int) -> dict:
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _contract(
    observed: list[str],
    expected: list[str] | None,
    baseline: list[str] | None = None,
) -> dict:
    """Compare observed field names against the contract and the last probe.

    Two separate questions, deliberately not conflated:

    `missing` is a contract break — ingestion depends on that field and it is gone.
    That fails the run.

    `added` / `dropped` are drift against `observed_fields_at_probe`, the full field
    list recorded when this endpoint was last probed. An endpoint can return a
    hundred fields we do not use; reporting all of them as "unexpected" on every run
    buries the one that matters. Drift is reported and not fatal — unless a dropped
    field is also in `expected_fields`, in which case it is already a break.
    """
    expected = expected or []
    obs, exp = set(observed), set(expected)
    base = set(baseline) if baseline else None
    out = {
        "n_fields": len(obs),
        "missing": sorted(exp - obs),      # we depend on it; the API does not have it
        "matched": sorted(obs & exp),
        "contract_ok": not (exp - obs),
    }
    if base is None:
        # No baseline recorded yet: everything outside the contract is new to us.
        out["baseline_recorded"] = False
        out["unexpected"] = sorted(obs - exp)
    else:
        out["baseline_recorded"] = True
        out["added"] = sorted(obs - base)     # API grew a field since the last probe
        out["dropped"] = sorted(base - obs)   # API lost a field since the last probe
    return out


def _null_audit(rows: list[dict]) -> dict:
    """fiscaldata returns everything as strings and nulls as the string 'null'.

    Record which fields actually do that, so the typed parsing layer is built from
    observation rather than assumption.
    """
    string_null_fields, non_string_fields = [], []
    for row in rows:
        for key, value in row.items():
            if isinstance(value, str) and value.strip().lower() == "null":
                string_null_fields.append(key)
            elif not isinstance(value, str) and value is not None:
                non_string_fields.append(f"{key}:{type(value).__name__}")
    return {
        "fields_with_string_null": sorted(set(string_null_fields)),
        "fields_not_string_typed": sorted(set(non_string_fields)),
    }


# --------------------------------------------------------------------------- #
# fiscaldata
# --------------------------------------------------------------------------- #

def probe_fiscaldata(cfg: dict, timeout: int) -> dict:
    base = cfg["base_url"].rstrip("/") + "/"
    results = {}

    for name, spec in cfg["endpoints"].items():
        url = base + spec["path"]
        date_field = spec.get("date_field", "record_date")
        entry: dict = {"url": url, "path": spec["path"], "purpose": spec.get("purpose")}

        try:
            # Newest rows: gives us field names, live sample values and latest date.
            latest = _get_json(url, {"page[size]": 2, "sort": f"-{date_field}"}, timeout)
            rows = latest.get("data", [])
            meta = latest.get("meta", {})

            observed = sorted(rows[0].keys()) if rows else sorted(meta.get("dataTypes", {}).keys())

            # Oldest row: establishes true coverage start rather than assuming ~2001.
            oldest = _get_json(url, {"page[size]": 1, "sort": date_field}, timeout)
            oldest_rows = oldest.get("data", [])

            # Probe for fields we hope exist but did not put in the contract
            # (e.g. low/median yield, which would give us a real free tail proxy).
            extras_present = [f for f in spec.get("probe_extra_fields", []) if f in observed]

            entry.update({
                "status": "ok",
                "observed_fields": observed,
                "data_types": meta.get("dataTypes", {}),
                "labels": meta.get("labels", {}),
                "total_rows_available": meta.get("total-count"),
                "latest_date": rows[0].get(date_field) if rows else None,
                "earliest_date": oldest_rows[0].get(date_field) if oldest_rows else None,
                "contract": _contract(
                    observed,
                    spec.get("expected_fields"),
                    spec.get("observed_fields_at_probe"),
                ),
                "probe_extra_fields_present": extras_present,
                "probe_extra_fields_absent": [
                    f for f in spec.get("probe_extra_fields", []) if f not in observed
                ],
                "null_audit": _null_audit(rows),
                "sample_rows": rows[:2],
                "critical_unknowns": spec.get("critical_unknowns", []),
            })
        except Exception as exc:  # noqa: BLE001 - probe reports failures, never raises
            entry.update({
                "status": "error",
                "error": _redact(f"{type(exc).__name__}: {exc}"),
                "critical_unknowns": spec.get("critical_unknowns", []),
            })

        results[name] = entry

    return results


# --------------------------------------------------------------------------- #
# FRED
# --------------------------------------------------------------------------- #

def probe_fred(cfg: dict, api_key: str | None, timeout: int) -> dict:
    if not api_key:
        return {"status": "skipped", "reason": "FRED_API_KEY not set in environment"}

    base = cfg["base_url"].rstrip("/") + "/"
    results: dict = {"status": "ok", "series": {}}

    for group, series_ids in cfg["series"].items():
        for sid in series_ids:
            try:
                meta = _get_json(
                    base + "series",
                    {"series_id": sid, "api_key": api_key, "file_type": "json"},
                    timeout,
                )
                info = meta["seriess"][0]
                obs = _get_json(
                    base + "series/observations",
                    {
                        "series_id": sid, "api_key": api_key, "file_type": "json",
                        "sort_order": "desc", "limit": 3,
                    },
                    timeout,
                )
                results["series"][sid] = {
                    "group": group,
                    "status": "ok",
                    "title": info.get("title"),
                    "frequency": info.get("frequency_short"),
                    "units": info.get("units_short"),
                    "seasonal_adjustment": info.get("seasonal_adjustment_short"),
                    "observation_start": info.get("observation_start"),
                    "observation_end": info.get("observation_end"),
                    "last_updated": info.get("last_updated"),
                    "latest_observations": obs.get("observations", []),
                }
            except Exception as exc:  # noqa: BLE001
                results["series"][sid] = {
                    "group": group,
                    "status": "error",
                    "error": _redact(f"{type(exc).__name__}: {exc}"),
                }

    return results


# --------------------------------------------------------------------------- #
# NY Fed ACM
# --------------------------------------------------------------------------- #

def probe_nyfed(cfg: dict, timeout: int, outdir: pathlib.Path) -> dict:
    url = cfg["url"]
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()

        raw = outdir / "ACMTermPremium_sample.bin"
        raw.write_bytes(resp.content)

        entry: dict = {
            "status": "ok",
            "url": url,
            "content_type": resp.headers.get("Content-Type"),
            "content_length_bytes": len(resp.content),
            "saved_sample": str(raw.relative_to(REPO_ROOT)),
        }

        # Format is not guaranteed to be .xls despite the extension — try both engines.
        import io

        import pandas as pd

        last_error = None
        for engine in ("xlrd", "openpyxl", None):
            try:
                df = pd.read_excel(io.BytesIO(resp.content), engine=engine)
                entry.update({
                    "parsed_with_engine": engine or "pandas-default",
                    "columns": [str(c) for c in df.columns],
                    "n_rows": int(len(df)),
                    "head": json.loads(df.head(3).to_json(orient="records", date_format="iso")),
                    "tail": json.loads(df.tail(3).to_json(orient="records", date_format="iso")),
                    "series_of_interest_present": [
                        s for s in cfg.get("series_of_interest", [])
                        if s in [str(c) for c in df.columns]
                    ],
                })
                break
            except Exception as exc:  # noqa: BLE001
                last_error = _redact(f"{type(exc).__name__}: {exc}")
        else:
            entry["parse_error"] = last_error

        return entry
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "url": url, "error": _redact(f"{type(exc).__name__}: {exc}")}


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #

def write_markdown(report: dict, path: pathlib.Path) -> None:
    L: list[str] = [
        "# Source probe results",
        "",
        f"- Probe run (UTC): `{report['probe_timestamp_utc']}`",
        "",
        "Field names below are **observed from live responses**. Anything marked "
        "MISSING means `config/sources.yaml` expected a field the API does not "
        "return — the contract is wrong and must be corrected before ingestion "
        "is written against it.",
        "",
    ]

    fd = report.get("fiscaldata", {})
    if fd:
        L += ["## Treasury Fiscal Data", "",
              "| endpoint | status | rows | coverage | contract |", "|---|---|---|---|---|"]
        for name, e in fd.items():
            if e.get("status") != "ok":
                L.append(f"| `{name}` | **ERROR** | – | – | {e.get('error', '')[:80]} |")
                continue
            c = e["contract"]
            if not c["contract_ok"]:
                verdict = f"**{len(c['missing'])} MISSING**"
            elif c.get("added") or c.get("dropped"):
                verdict = f"OK, drift +{len(c.get('added', []))}/-{len(c.get('dropped', []))}"
            else:
                verdict = "OK"
            cov = f"{e.get('earliest_date')} → {e.get('latest_date')}"
            L.append(
                f"| `{name}` | ok | {e.get('total_rows_available')} | {cov} | {verdict} |"
            )
        L.append("")

        for name, e in fd.items():
            L += [f"### `{name}`", ""]
            if e.get("status") != "ok":
                L += [f"**Probe failed:** `{e.get('error')}`", ""]
                if e.get("critical_unknowns"):
                    L += ["Unresolved:", ""] + [f"- {u}" for u in e["critical_unknowns"]] + [""]
                continue
            c = e["contract"]
            L += [f"`{e['url']}`", "",
                  f"- Coverage: **{e.get('earliest_date')} → {e.get('latest_date')}** "
                  f"({e.get('total_rows_available')} rows)",
                  f"- Observed fields ({c['n_fields']}): "
                  + ", ".join(f"`{f}`" for f in e["observed_fields"]), ""]
            if c["missing"]:
                L += ["- **MISSING (contracted, not returned):** "
                      + ", ".join(f"`{f}`" for f in c["missing"]), ""]
            if c.get("unexpected"):
                L += ["- Returned, not in contract (no baseline recorded yet): "
                      + ", ".join(f"`{f}`" for f in c["unexpected"]), ""]
            if c.get("added"):
                L += ["- **ADDED since last probe:** "
                      + ", ".join(f"`{f}`" for f in c["added"]), ""]
            if c.get("dropped"):
                L += ["- **DROPPED since last probe:** "
                      + ", ".join(f"`{f}`" for f in c["dropped"]), ""]
            if c["contract_ok"] and not c.get("added") and not c.get("dropped") \
                    and c.get("baseline_recorded"):
                L += ["- No field drift since the last probe.", ""]
            if e.get("probe_extra_fields_present"):
                L += ["- **Opportunistic fields FOUND:** "
                      + ", ".join(f"`{f}`" for f in e["probe_extra_fields_present"]), ""]
            if e.get("probe_extra_fields_absent"):
                L += ["- Opportunistic fields absent: "
                      + ", ".join(f"`{f}`" for f in e["probe_extra_fields_absent"]), ""]
            na = e.get("null_audit", {})
            if na.get("fields_not_string_typed"):
                L += ["- Non-string typed fields: "
                      + ", ".join(f"`{f}`" for f in na["fields_not_string_typed"]), ""]
            if e.get("critical_unknowns"):
                L += ["Open questions this probe was meant to answer:", ""] \
                     + [f"- {u}" for u in e["critical_unknowns"]] + [""]

    fr = report.get("fred", {})
    if fr:
        L += ["## FRED", ""]
        if fr.get("status") == "skipped":
            L += [f"Skipped: {fr.get('reason')}", ""]
        else:
            L += ["| series | status | freq | units | coverage | last updated |",
                  "|---|---|---|---|---|---|"]
            for sid, s in fr.get("series", {}).items():
                if s.get("status") != "ok":
                    L.append(f"| `{sid}` | **ERROR** | – | – | – | {s.get('error', '')[:40]} |")
                else:
                    L.append(
                        f"| `{sid}` | ok | {s.get('frequency')} | {s.get('units')} | "
                        f"{s.get('observation_start')} → {s.get('observation_end')} | "
                        f"{s.get('last_updated')} |"
                    )
            L.append("")

    ny = report.get("nyfed_acm", {})
    if ny:
        L += ["## NY Fed ACM term premium", ""]
        if ny.get("status") != "ok":
            L += [f"**Probe failed:** `{ny.get('error')}`", ""]
        else:
            L += [f"- URL: `{ny.get('url')}`",
                  f"- Content-Type: `{ny.get('content_type')}`, "
                  f"{ny.get('content_length_bytes')} bytes",
                  f"- Parsed with: `{ny.get('parsed_with_engine', 'FAILED')}`"]
            if ny.get("columns"):
                L += [f"- Rows: {ny.get('n_rows')}",
                      "- Columns: " + ", ".join(f"`{c}`" for c in ny["columns"]),
                      "- Series of interest present: "
                      + (", ".join(f"`{s}`" for s in ny.get("series_of_interest_present", []))
                         or "**none found**")]
            if ny.get("parse_error"):
                L += [f"- **Parse error:** `{ny['parse_error']}`"]
            L.append("")

    path.write_text("\n".join(L), encoding="utf-8")


# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", choices=["fiscaldata", "fred", "nyfed"], action="append")
    ap.add_argument("--timeout", type=int, default=TIMEOUT_DEFAULT)
    args = ap.parse_args()

    import os

    register_secret(os.environ.get("FRED_API_KEY"))

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    run_all = not args.only
    want = set(args.only or [])

    stamp = dt.datetime.now(dt.timezone.utc)
    outdir = REPO_ROOT / "docs" / "source_probe" / stamp.strftime("%Y-%m-%d")
    outdir.mkdir(parents=True, exist_ok=True)

    # A partial run must not erase the rest of the day's evidence. `--only fred`
    # writes a report containing only FRED, so replacing the file wholesale would
    # silently drop the fiscaldata and NY Fed sections probed an hour earlier —
    # leaving a file that looks like a complete run of one source.
    existing_path = outdir / "probe.json"
    report: dict = {}
    if existing_path.exists():
        try:
            report = json.loads(existing_path.read_text(encoding="utf-8"))
            if args.only:
                print(f"merging into existing evidence for {stamp:%Y-%m-%d}", flush=True)
        except json.JSONDecodeError:
            report = {}

    report["probe_timestamp_utc"] = stamp.isoformat()
    report["config_version"] = cfg["meta"]["version"]

    if run_all or "fiscaldata" in want:
        print("probing fiscaldata ...", flush=True)
        report["fiscaldata"] = probe_fiscaldata(cfg["fiscaldata"], args.timeout)
    if run_all or "fred" in want:
        print("probing FRED ...", flush=True)
        report["fred"] = probe_fred(cfg["fred"], os.environ.get("FRED_API_KEY"), args.timeout)
    if run_all or "nyfed" in want:
        print("probing NY Fed ACM ...", flush=True)
        report["nyfed_acm"] = probe_nyfed(cfg["nyfed_acm"], args.timeout, outdir)

    # Defence in depth: scrub the serialised report as a whole, so a secret
    # reaching it by some path not anticipated above still cannot be written.
    (outdir / "probe.json").write_text(
        _redact(json.dumps(report, indent=2, default=str)), encoding="utf-8"
    )
    write_markdown(report, outdir / "README.md")

    # ---- summarise to stdout and set exit status -------------------------- #
    failures: list[str] = []
    for name, e in report.get("fiscaldata", {}).items():
        if e.get("status") != "ok":
            failures.append(f"fiscaldata/{name}: {e.get('error')}")
        elif not e["contract"]["contract_ok"]:
            failures.append(f"fiscaldata/{name}: missing {e['contract']['missing']}")
    fr = report.get("fred", {})
    if fr.get("status") == "ok":
        failures += [f"fred/{s}: {v.get('error')}"
                     for s, v in fr["series"].items() if v.get("status") != "ok"]
    ny = report.get("nyfed_acm", {})
    if ny and ny.get("status") != "ok":
        failures.append(f"nyfed_acm: {ny.get('error')}")

    print(f"\nEvidence written to {outdir.relative_to(REPO_ROOT)}/")
    if failures:
        print(f"\n{len(failures)} contract failure(s) / unreachable source(s):")
        for f in failures:
            print(f"  - {f}")
        print("\nFix config/sources.yaml to match observed reality before writing ingestion.")
        return 1

    print("\nAll probed sources reachable and matching their contracts.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
