#!/usr/bin/env python3
"""Pull sources, normalize, validate, and write the processed store.

The layering the app depends on, in one place: ingestion writes `data/raw/`
exactly as retrieved, transformation writes `data/processed/`, and validation
sits between them with the authority to stop the run. The Streamlit app reads
`data/processed/` and nothing else.

Validation failures exit non-zero. A refresh that half-succeeded and left a
stale-but-plausible processed store is the failure mode worth being loud about,
so the processed file is only replaced once its checks have passed.

Usage:
    python scripts/refresh.py                  # all Phase 1 tables
    python scripts/refresh.py --only debt_outstanding
    python scripts/refresh.py --no-raw         # skip the raw archive
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.fiscaldata import (  # noqa: E402
    FiscalDataClient,
    parse_endpoint,
    write_raw,
)
from src.transformation.normalize import normalize_debt_outstanding  # noqa: E402
from src.validation.reconciliation import reconcile_components_to_total  # noqa: E402

PROCESSED = REPO_ROOT / "data" / "processed"
THRESHOLDS = REPO_ROOT / "config" / "thresholds.yaml"


def _thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))


def build_debt_outstanding(client: FiscalDataClient, *, keep_raw: bool) -> pd.DataFrame:
    """mspd_table_1 → debt_outstanding, reconciled against the published total."""
    print("  fetching mspd_table_1 ...", flush=True)
    result = client.fetch("mspd_table_1")
    print(f"    {result.n_rows} rows over {result.n_pages} page(s)")

    if keep_raw:
        raw = write_raw(result)
        print(f"    raw → {raw.relative_to(REPO_ROOT)}")

    typed, report = parse_endpoint(result)
    report.raise_if_failed()
    print(f"    parsed, {report.total_parse_failures} coercion failure(s)")

    table = normalize_debt_outstanding(typed, retrieval_date=result.retrieval_date)
    print(f"    normalized to {len(table)} rows, "
          f"{table.observation_date.min():%Y-%m} → {table.observation_date.max():%Y-%m}")

    tol = _thresholds()["validation"]["reconciliation_tolerance_pct"]
    check = reconcile_components_to_total(table, tolerance_pct=tol)
    print(f"    reconciliation: {check.n_periods} periods, worst "
          f"{check.max_abs_diff_pct:.2e}% (tolerance {tol}%)")
    check.raise_if_failed()

    return table


BUILDERS = {"debt_outstanding": build_debt_outstanding}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", choices=sorted(BUILDERS), action="append")
    ap.add_argument("--no-raw", action="store_true", help="skip the raw archive")
    args = ap.parse_args()

    wanted = args.only or sorted(BUILDERS)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    client = FiscalDataClient()

    for name in wanted:
        print(f"\n{name}:")
        try:
            table = BUILDERS[name](client, keep_raw=not args.no_raw)
        except Exception as exc:  # noqa: BLE001 - the point is to fail loudly
            print(f"\n  FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

        target = PROCESSED / f"{name}.parquet"
        table.to_parquet(target, index=False)
        print(f"    processed → {target.relative_to(REPO_ROOT)}")

    print("\nRefresh complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
