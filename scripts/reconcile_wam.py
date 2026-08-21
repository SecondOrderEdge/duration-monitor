"""Reconcile our computed WAM against Treasury's published monthly series.

Treasury publishes it after all. The quarterly release workbook
(`.../system/files/221/<year>-<n>-Quarter.xls`) carries a sheet
"Avg. mat. of debt outstanding" holding

    Average Maturity of Treasury Marketable Securities--Total Outstanding (in months)
    Year | Jan | Feb | Mar | ... | Dec

as a monthly grid back to 2000 — our metric, our population, our period. Four
probe runs concluded it did not exist because the workbook was being fetched and
decoded as UTF-8, which yields mojibake without raising, so the file counted as
searched while carrying nothing readable.

Two traps this module exists to avoid, both already hit once in this project:

**The wrong series.** The same workbook carries "Average Length of Marketable
Interest-Bearing Public Debt", which is the PRIVATE INVESTORS measure and a
different population. The sheet is selected by its own title, not by position.

**Units.** Treasury publishes integer months; we compute years. Conversion
happens once, at comparison, and both figures are reported.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import re
import sys

import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.probe_tbac import fetch  # noqa: E402

OUT_DIR = REPO_ROOT / "docs" / "source_probe" / "wam_reference"
WORKBOOK = "https://home.treasury.gov/system/files/221/2026-3rd-Quarter.xls"

# The sheet must describe TOTAL OUTSTANDING and be quoted in months. "Average
# Length" is deliberately excluded: that is the private-investor series.
WANTED_TITLE = re.compile(
    r"average maturity.*(?:total )?outstanding.*months|average maturity of treasury"
    r" marketable securities", re.I
)
EXCLUDE_TITLE = re.compile(r"average length|private investors", re.I)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ReconciliationError(RuntimeError):
    """The workbook does not hold what this module needs it to hold."""


def find_series(payload: bytes) -> tuple[pd.Series, str]:
    """The published monthly average-maturity series, in months.

    Returns (series indexed by month Period, sheet title actually matched). The
    title is returned so the caller can record WHICH series was read — the same
    workbook holds a similarly named one for a different population.
    """
    sheets = pd.read_excel(io.BytesIO(payload), sheet_name=None, header=None)

    for name, frame in sheets.items():
        blob = " ".join(str(c) for c in frame.head(6).to_numpy().ravel() if str(c) != "nan")
        if not WANTED_TITLE.search(blob) or EXCLUDE_TITLE.search(blob):
            continue

        # Find the header row by content rather than by a fixed offset: these
        # workbooks carry a title block of varying height above the grid.
        header_row = None
        for index, row in frame.iterrows():
            cells = [str(c).strip() for c in row.tolist()]
            if "Year" in cells and "Jan" in cells:
                header_row = index
                break
        if header_row is None:
            continue

        header = [str(c).strip() for c in frame.loc[header_row].tolist()]
        body = frame.loc[header_row + 1:].copy()
        body.columns = header

        records = {}
        for _, row in body.iterrows():
            year = pd.to_numeric(row.get("Year"), errors="coerce")
            if pd.isna(year) or not (1970 < year < 2100):
                continue
            for position, month in enumerate(MONTHS, start=1):
                value = pd.to_numeric(row.get(month), errors="coerce")
                if pd.notna(value):
                    records[pd.Period(f"{int(year)}-{position:02d}", freq="M")] = float(value)

        if not records:
            continue
        series = pd.Series(records).sort_index()
        series.name = "published_months"
        return series, f"{name}: {blob[:120]}"

    raise ReconciliationError(
        "no sheet matched a total-outstanding average-maturity grid; sheets were "
        f"{list(sheets)}"
    )


def compare(ours: pd.DataFrame, published: pd.Series) -> pd.DataFrame:
    """Join the two series on month and difference them, in months."""
    mine = ours.copy()
    mine["period"] = pd.PeriodIndex(pd.to_datetime(mine["observation_date"]), freq="M")
    mine = mine.set_index("period")["wam_years"] * 12
    mine.name = "our_months"

    # Named here rather than relying on the caller. An unnamed Series concats to
    # a column called 0, and every lookup below then fails on a KeyError that
    # says nothing about the cause.
    published = published.rename("published_months")

    joined = pd.concat([published, mine], axis=1, join="inner")
    joined["difference_months"] = joined["our_months"] - joined["published_months"]
    # Treasury publishes whole months, so anything inside half a month is
    # rounding and not a discrepancy worth naming.
    joined["within_rounding"] = joined["difference_months"].abs() <= 0.5
    return joined


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", default=WORKBOOK)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    print(f"fetching {args.workbook}", flush=True)
    record = fetch(args.workbook, args.timeout, max_bytes=25_000_000)
    payload = record.pop("_payload", None)
    if payload is None:
        print(f"  FAILED: {record.get('error') or record.get('skipped')}", file=sys.stderr)
        return 1

    published, title = find_series(payload)
    print(f"  matched sheet — {title}")
    print(f"  published series: {len(published)} months, "
          f"{published.index.min()} → {published.index.max()}, "
          f"latest {published.iloc[-1]:.0f} months")

    wam_path = REPO_ROOT / "data" / "processed" / "wam.parquet"
    if not wam_path.exists():
        print("  no wam.parquet; run `python scripts/refresh.py --only wam`", file=sys.stderr)
        return 1

    joined = compare(pd.read_parquet(wam_path), published)
    if joined.empty:
        print("  NO OVERLAP between the published series and ours", file=sys.stderr)
        return 1

    diff = joined["difference_months"]
    inside = int(joined["within_rounding"].sum())
    print(f"\n  overlap: {len(joined)} months, "
          f"{joined.index.min()} → {joined.index.max()}")
    print(f"  ours minus Treasury: mean {diff.mean():+.2f}mo  "
          f"median {diff.median():+.2f}mo  "
          f"min {diff.min():+.2f}  max {diff.max():+.2f}")
    print(f"  within half a month (Treasury publishes integers): "
          f"{inside}/{len(joined)} ({inside / len(joined):.0%})")

    worst = diff.abs().sort_values(ascending=False).head(5)
    print("  largest gaps:")
    for period in worst.index:
        print(f"    {period}: ours {joined.loc[period, 'our_months']:.1f}mo vs "
              f"Treasury {joined.loc[period, 'published_months']:.0f}mo "
              f"({diff.loc[period]:+.1f})")

    # The check, not just the report. A reconciliation that only prints is one
    # nobody reads until they already suspect something.
    import yaml

    cfg = yaml.safe_load(
        (REPO_ROOT / "config" / "thresholds.yaml").read_text(encoding="utf-8")
    )["validation"].get("wam_vs_treasury") or {}
    judge_from = pd.Period(str(cfg.get("judge_from", "2008-01")), freq="M")
    limit = float(cfg.get("max_median_abs_difference_months", 0.5))
    modern = joined[joined.index >= judge_from]["difference_months"]
    breached = bool(len(modern)) and abs(modern.median()) > limit
    print(f"\n  check: median |difference| from {judge_from} is "
          f"{abs(modern.median()):.3f} months against a {limit} limit "
          f"({len(modern)} months) — {'FAIL' if breached else 'ok'}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "check_from": str(judge_from),
        "check_limit_months": limit,
        "check_median_abs_months": round(float(abs(modern.median())), 4),
        "check_passed": not breached,
        "workbook": args.workbook,
        "sheet": title,
        "published_months": len(published),
        "overlap_months": len(joined),
        "overlap_from": str(joined.index.min()),
        "overlap_to": str(joined.index.max()),
        "mean_difference_months": round(float(diff.mean()), 3),
        "median_difference_months": round(float(diff.median()), 3),
        "max_abs_difference_months": round(float(diff.abs().max()), 3),
        "within_half_month": inside,
        "within_half_month_share": round(inside / len(joined), 4),
    }
    (OUT_DIR / "wam_vs_treasury.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    joined.reset_index().rename(columns={"index": "period"}).assign(
        period=lambda f: f["period"].astype(str)
    ).to_csv(OUT_DIR / "wam_vs_treasury.csv", index=False)
    print(f"\n  → {(OUT_DIR / 'wam_vs_treasury.json').relative_to(REPO_ROOT)}")
    if breached:
        print("::error::WAM has drifted from Treasury's published series beyond "
              f"{limit} months since {judge_from}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
