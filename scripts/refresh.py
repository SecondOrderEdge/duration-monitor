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
from src.calculations.wam import wam_series  # noqa: E402
from src.ingestion.fred import FredClient, MissingCredential  # noqa: E402
from src.ingestion.nyfed import detect_revisions, fetch_acm  # noqa: E402
from src.ingestion.eurostat import EurostatClient  # noqa: E402
from src.calculations.issuance import (  # noqa: E402
    bill_share,
    cash_adjusted_bill_funding,
    incremental_bill_funding,
    net_issuance,
)
from src.signals.duration_shift_score import (  # noqa: E402
    build_factors,
    resolve_variant,
    classify_regime,
    duration_shift_score,
    expanding_weights,
    percentile_ranks,
    score_band,
)
from src.signals.auction_stress import (  # noqa: E402
    DEFAULT_COMPONENTS,
    Component,
    auction_stress_score,
    long_end_stress,
)
from src.transformation.normalize import (  # noqa: E402
    EUROSTAT_CENTRAL_GOVERNMENT,
    MILLIONS,
    extract_subtotals,
    normalize_eurostat_debt,
    month_end_cash_balance,
    normalize_cash_balance,
    normalize_auctions,
    normalize_debt_outstanding,
    normalize_securities_detail,
    unclassified_subtotal_rows,
    wam_input,
)
from src.validation.quality import QualityLog, check_staleness  # noqa: E402
from src.validation.reconciliation import (  # noqa: E402
    reconcile_components_to_total,
    reconcile_detail_to_published_subtotal,
)

PROCESSED = REPO_ROOT / "data" / "processed"
THRESHOLDS = REPO_ROOT / "config" / "thresholds.yaml"

EURO_DATASET = "gov_10q_ggdebt"
# Phase 3 scope. Not the euro area as a whole: these are the three sovereigns
# whose quantity factors Eurostat actually supports (docs/phase3_source_assessment.md).
EURO_COUNTRIES = ["DE", "FR", "IT"]

# Builders append informational notes here; main() folds them into the event log.
QUALITY_NOTES: list[dict] = []


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


def build_wam(client: FiscalDataClient, *, keep_raw: bool) -> pd.DataFrame:
    """mspd_table_3_market → WAM and maturity-bucket series.

    Only the derived series is returned for the processed store. The CUSIP-level
    detail behind it is ~150k rows and would be rewritten in full on every refresh,
    so it stays in `data/raw/` (git-ignored) with only the latest snapshot
    published alongside — Deviation D7.
    """
    print("  fetching mspd_table_3_market ...", flush=True)
    result = client.fetch("mspd_table_3_market")
    print(f"    {result.n_rows} rows over {result.n_pages} page(s)")

    if keep_raw:
        raw = write_raw(result)
        print(f"    raw → {raw.relative_to(REPO_ROOT)}")

    typed, report = parse_endpoint(result)
    report.raise_if_failed()

    securities = normalize_securities_detail(typed, retrieval_date=result.retrieval_date)
    print(f"    {len(securities)} security-months over "
          f"{securities.observation_date.nunique()} months")

    # The check that makes WAM publishable: the security rows WAM is weighted by
    # must reproduce Treasury's own published per-class unmatured subtotal. If they
    # do not, the weights are wrong and nothing downstream would reveal it.
    validation = _thresholds()["validation"]
    check = reconcile_detail_to_published_subtotal(
        securities,
        extract_subtotals(typed),
        tolerance_pct=validation["reconciliation_tolerance_pct"],
        known_defects=validation.get("known_subtotal_defects") or [],
    )
    print(f"    detail vs published subtotal: {check.n_periods} (month, class) pairs, "
          f"worst {check.max_abs_diff_pct:.2e}%")
    check.raise_if_failed()

    orphans = unclassified_subtotal_rows(typed)
    orphans = orphans[
        ~orphans["security_class1_desc"].astype(str).isin(
            ["Federal Financing Bank", "Total Marketable"]
        )
    ]
    if len(orphans):
        detail = (
            f"{len(orphans)} row(s) with no maturity date and no recognisable "
            f"subtotal label, e.g. CUSIP "
            f"{orphans['security_class2_desc'].astype(str).iloc[0]} at "
            f"{orphans['record_date'].iloc[0]:%Y-%m}. Excluded from WAM — there is "
            "no duration to compute without a maturity — and reported rather than "
            "silently dropped."
        )
        print(f"    note: {detail}")
        QUALITY_NOTES.append(
            {"source": "wam", "endpoint": "mspd_table_3_market",
             "event_type": "parse_failure", "severity": "warning", "detail": detail}
        )

    basis = _thresholds()["wam"]["tips_weighting_basis"]
    series = wam_series(wam_input(securities, basis=basis))
    series["amount_basis"] = basis
    series["source"] = "fiscaldata/mspd_table_3_market"
    series["retrieval_date"] = result.retrieval_date
    series["country"] = "US"
    print(f"    WAM {series.wam_years.iloc[-1]:.2f}y at "
          f"{series.observation_date.iloc[-1]:%Y-%m} (weighted on {basis})")

    # The latest CUSIP snapshot is small and useful on the page; the history is not.
    latest = securities[securities.observation_date == securities.observation_date.max()]
    snapshot = PROCESSED / "securities_detail_latest.parquet"
    latest.to_parquet(snapshot, index=False)
    print(f"    latest snapshot ({len(latest)} securities) → "
          f"{snapshot.relative_to(REPO_ROOT)}")

    return series


def build_term_premium(client: FiscalDataClient, *, keep_raw: bool) -> pd.DataFrame:
    """NY Fed ACM term premium, with revision detection against the prior vintage.

    ACM is model output and is re-estimated retroactively, so a value dated 2010
    can change between pulls. Overwriting silently would make a backtest
    irreproducible with no trace of why, so changed history is counted and flagged.
    """
    print("  fetching NY Fed ACM workbook ...", flush=True)
    table, retrieved = fetch_acm()
    print(f"    {len(table)} rows, {table.date.nunique()} dates, "
          f"{table.date.min():%Y-%m-%d} → {table.date.max():%Y-%m-%d}")

    existing = PROCESSED / "term_premium.parquet"
    if existing.exists():
        report = detect_revisions(pd.read_parquet(existing), table)
        print(f"    revision check: {report.n_compared} overlapping observations, "
              f"{len(report.changed)} changed")
        if report.has_revisions:
            table["revision_flag"] = table.set_index(["date", "maturity", "model"]).index.isin(
                report.changed.set_index(["date", "maturity", "model"]).index
            )
            worst = report.changed["abs_change"].max()
            print(f"    ACM re-estimated: largest historical change {worst:.4f}pp")
    else:
        print("    no prior vintage to compare against")

    # Storage boundary (Deviation D7). The full daily series back to 1961 is 449KB
    # and would be rewritten on every scheduled run, which is permanent git
    # history for a file the app re-reads whole. The processed store keeps daily
    # data from 1991: that is a ten-year lead-in before the 2001 backtest start,
    # which is exactly the minimum history D1 requires before a point-in-time
    # percentile may publish. Earlier history stays in data/raw, git-ignored, and
    # is reproducible by re-running ingestion.
    boundary = pd.Timestamp(_thresholds().get("storage", {}).get(
        "term_premium_processed_start", "1991-01-01"
    ))
    full_rows = len(table)
    table = table[table["date"] >= boundary].copy()
    print(f"    processed store keeps {len(table)} of {full_rows} rows "
          f"(daily from {boundary:%Y}; earlier history in data/raw)")

    for column in ("country", "maturity", "model", "units", "source"):
        if column in table.columns:
            table[column] = table[column].astype("category")
    table["value"] = table["value"].astype("float32")

    return table


def build_rates(client: FiscalDataClient, *, keep_raw: bool) -> pd.DataFrame:
    """FRED series. Requires FRED_API_KEY."""
    print("  fetching FRED series ...", flush=True)
    fred = FredClient()
    configured = fred.configured_series()
    table = fred.fetch_many(configured)
    print(f"    {len(table)} observations across {table.series_id.nunique()} series")

    gaps = table[table["value"].isna()].groupby("series_id").size()
    if len(gaps):
        print(f"    documented missing observations: {gaps.to_dict()}")
    return table


def build_auctions(client: FiscalDataClient, *, keep_raw: bool) -> pd.DataFrame:
    """auctions_query → per-auction stress score and the long-end rolling series."""
    print("  fetching auctions_query ...", flush=True)
    result = client.fetch("auctions_query")
    print(f"    {result.n_rows} rows over {result.n_pages} page(s)")

    if keep_raw:
        raw = write_raw(result)
        print(f"    raw → {raw.relative_to(REPO_ROOT)}")

    typed, report = parse_endpoint(result)
    report.raise_if_failed()

    auctions = normalize_auctions(typed, retrieval_date=result.retrieval_date)
    print(f"    {len(auctions)} held auctions, "
          f"{auctions.auction_date.min():%Y-%m} → {auctions.auction_date.max():%Y-%m} "
          f"({auctions.attrs['n_unheld_dropped']} scheduled-but-unheld dropped; "
          f"{auctions.attrs['n_without_results']} held with results never published)")

    cfg = _thresholds()["auctions"]
    weights = yaml.safe_load(
        (REPO_ROOT / "config" / "factor_weights.yaml").read_text(encoding="utf-8")
    )["auction_stress_components"]
    components = {
        name: Component(spec.column, sign=spec.sign, weight=float(weights.get(name, 0.0)))
        for name, spec in DEFAULT_COMPONENTS.items()
    }
    active = {n: c.weight for n, c in components.items() if c.weight > 0}
    print(f"    components: {active}")

    # Bidder detail only exists from 2008; earlier auctions are kept but excluded
    # from the composite so a reduced factor set is never scored as a full one.
    start = pd.Timestamp(cfg["composite_start_date"])
    scored_input = (
        auctions if cfg["include_pre_2008_in_composite"]
        else auctions[auctions.auction_date >= start]
    )
    scored = auction_stress_score(
        scored_input,
        components=components,
        trailing_auctions=cfg["trailing_auctions"],
        min_trailing=cfg["min_trailing_auctions"],
        min_components=cfg["min_components"],
        scale_sigma=cfg["scale_sigma"],
    )
    n_scored = int(scored["stress_score"].notna().sum())
    print(f"    scored {n_scored} of {len(scored)} auctions since "
          f"{start:%Y-%m} (min {cfg['min_trailing_auctions']} trailing per tenor)")

    rolling = long_end_stress(
        scored,
        terms=tuple(cfg["long_end_terms"]),
        window_days=cfg["long_end_window_days"],
        min_auctions=cfg["long_end_min_auctions"],
    )
    latest = rolling.dropna()
    if len(latest):
        print(f"    long-end stress {latest.iloc[-1]:+.1f} at {latest.index[-1]:%Y-%m-%d}")

    # The processed table is the SCORED universe. Auctions before the composite
    # start are normalized and archived in data/raw but not published here, so
    # their absence is recorded rather than left to look like the source having
    # no earlier history (Deviation D7, same boundary logic as term premium).
    excluded = auctions[auctions.auction_date < start]
    if len(excluded):
        detail = (
            f"{len(excluded)} auctions before {start:%Y-%m} are archived in "
            f"data/raw but excluded from the processed store, of which "
            f"{int((~excluded['has_results']).sum())} were held without published "
            "results (bid-to-cover was not reported before about 2000)"
        )
        print(f"    note: {detail}")
        QUALITY_NOTES.append(
            {"source": "auctions", "endpoint": "auctions_query",
             "event_type": "staleness", "severity": "info", "detail": detail}
        )

    rolling_frame = latest.reset_index()
    rolling_frame.columns = ["date", "long_end_stress"]
    rolling_frame["country"] = "US"
    rolling_frame.to_parquet(PROCESSED / "long_end_stress.parquet", index=False)
    print(f"    processed → data/processed/long_end_stress.parquet")

    return scored


def build_cash_balance(client: FiscalDataClient, *, keep_raw: bool) -> pd.DataFrame:
    """Daily Treasury General Account balance.

    Feeds the cash adjustment that separates borrowing which financed the deficit
    from borrowing which rebuilt the cash balance after a debt-ceiling episode
    (Deviation D5).
    """
    print("  fetching operating_cash_balance ...", flush=True)
    result = client.fetch("operating_cash_balance")
    print(f"    {result.n_rows} rows over {result.n_pages} page(s)")

    if keep_raw:
        raw = write_raw(result)
        print(f"    raw → {raw.relative_to(REPO_ROOT)}")

    typed, report = parse_endpoint(result)
    report.raise_if_failed()

    cash = normalize_cash_balance(typed, retrieval_date=result.retrieval_date)
    print(f"    TGA {len(cash)} days, {cash.date.min():%Y-%m} → {cash.date.max():%Y-%m}, "
          f"latest ${cash.balance.iloc[-1]/1e9:,.0f}bn")

    # The account was renamed twice and the endpoint restructured under the third
    # name. A break in the daily series is the symptom of having followed the
    # wrong column across the changeover, so it is checked rather than assumed.
    gaps = cash["date"].diff().dt.days
    if (gaps > 7).any():
        worst = cash.loc[gaps.idxmax(), "date"]
        QUALITY_NOTES.append(
            {"source": "cash_balance", "endpoint": "operating_cash_balance",
             "event_type": "staleness", "severity": "warning",
             "detail": f"gap of {int(gaps.max())} days in the TGA series before "
                       f"{worst:%Y-%m-%d}; check the account_type mapping"}
        )
        print(f"    WARNING: {int(gaps.max())}-day gap before {worst:%Y-%m-%d}")

    return cash


def build_euro_debt(client: FiscalDataClient, *, keep_raw: bool) -> pd.DataFrame:
    """Eurostat central-government debt securities for Germany, France and Italy.

    Phase 3's quantity inputs. Quarterly, because that is the only frequency any
    current euro-area publisher serves at the short/long split — the ECB dataflow
    that carried it monthly stopped in 2022-03 (docs/phase3_source_assessment.md).

    Nothing here has ever been fetched live: the development environment refuses
    Eurostat at CONNECT, so the decoder and the normalizer are tested against
    fixtures. This builder therefore prints what the response actually contained —
    dimensions, coverage, the instrument split, and the distribution of net
    borrowing that any ratio floor has to be calibrated against — rather than
    asserting the fixtures were right.
    """
    print("  fetching eurostat gov_10q_ggdebt ...", flush=True)
    eurostat = EurostatClient()
    result = eurostat.fetch(
        EURO_DATASET,
        geo=EURO_COUNTRIES,
        sector=EUROSTAT_CENTRAL_GOVERNMENT,
        unit="MIO_EUR",
        na_item=["F31", "F32"],
    )
    frame = result.frame
    print(f"    {result.n_values} values, {len(frame)} decoded rows")
    print(f"    published {result.updated!r}; label {str(result.label)[:70]!r}")

    # The decoder's whole risk is attributing a cell to the wrong series, and a
    # transposed frame is still well-formed. Printing the dimensions the response
    # actually carried is how a shape the fixtures never anticipated becomes
    # visible instead of being silently reinterpreted.
    dims = [c for c in frame.columns if c != "value"]
    print(f"    dimensions returned: {dims}")
    for dim in dims:
        seen = sorted(frame[dim].astype(str).unique())
        shown = seen if len(seen) <= 8 else seen[:4] + ["..."] + seen[-2:]
        print(f"      {dim}: {len(seen)} — {shown}")

    if keep_raw:
        outdir = REPO_ROOT / "data" / "raw" / "eurostat" / EURO_DATASET / (
            f"retrieved_date={result.retrieval_date:%Y-%m-%d}"
        )
        outdir.mkdir(parents=True, exist_ok=True)
        frame.astype("object").to_parquet(outdir / "part.parquet", index=False)
        print(f"    raw → {(outdir / 'part.parquet').relative_to(REPO_ROOT)}")

    debt = normalize_eurostat_debt(frame, retrieval_date=result.retrieval_date)

    # Coverage is asserted per country rather than in aggregate: three countries
    # summing to the expected number of rows would hide one of them being short.
    for country in EURO_COUNTRIES:
        rows = debt[debt["country"] == country]
        if rows.empty:
            raise ValueError(
                f"eurostat returned no usable rows for {country!r}; requested "
                f"{EURO_COUNTRIES} and decoded {sorted(debt['country'].unique())}"
            )
        quarters = rows["observation_date"].nunique()
        classes = sorted(rows["security_class"].astype(str).unique())
        latest = rows["observation_date"].max()
        bills = rows[(rows.security_class == "BILLS") & (rows.observation_date == latest)]
        total = rows[(rows.security_class == "TOTAL_MARKETABLE")
                     & (rows.observation_date == latest)]
        share = (float(bills.amount_outstanding.iloc[0]) /
                 float(total.amount_outstanding.iloc[0])) if len(bills) and len(total) else float("nan")
        print(f"    {country}: {quarters} quarters, "
              f"{rows.observation_date.min():%Y-Q}{rows.observation_date.min().quarter} → "
              f"{latest:%Y-Q}{latest.quarter}, classes {classes}, "
              f"bill share {share:.1%}, total €{float(total.amount_outstanding.iloc[0])/1e9:,.0f}bn")

        if set(classes) != {"BILLS", "COUPONS", "TOTAL_MARKETABLE"}:
            QUALITY_NOTES.append(
                {"source": "euro_debt", "endpoint": EURO_DATASET,
                 "event_type": "contract_break", "severity": "error",
                 "detail": f"{country} carries {classes}; the quantity factors need "
                           "both F31 short-term and F32 long-term"}
            )

    # A country that stopped publishing while the others continued would leave the
    # cross-country comparison silently mismatched in time, so the latest quarter
    # is compared across countries rather than taken as one number.
    latest_by_country = debt.groupby("country", observed=True)["observation_date"].max()
    if latest_by_country.nunique() > 1:
        detail = ("euro-area countries end on different quarters: "
                  + ", ".join(f"{c} {d:%Y-%m}" for c, d in latest_by_country.items()))
        print(f"    WARNING: {detail}")
        QUALITY_NOTES.append(
            {"source": "euro_debt", "endpoint": EURO_DATASET,
             "event_type": "staleness", "severity": "warning", "detail": detail}
        )

    # The ratio floor the US series uses is calibrated against the distribution of
    # |net borrowing| (thresholds.yaml, issuance.calibrated). No euro equivalent
    # has been calibrated yet, because until this run there was no live series to
    # calibrate against. The distribution is printed so that number comes from
    # data rather than from scaling the US one by a guess at relative size.
    for country in EURO_COUNTRIES:
        one = debt[(debt.country == country) & (debt.security_class != "TOTAL_MARKETABLE")]
        wide = one.pivot(index="observation_date", columns="security_class",
                         values="amount_outstanding")
        net_total = wide.sum(axis=1, min_count=1).diff().abs().dropna() / 1e6
        if len(net_total):
            q = net_total.quantile([0.10, 0.25, 0.50]).round(0)
            print(f"    {country} |net borrowing|/quarter (EUR mn): "
                  f"p10 {q.loc[0.10]:,.0f}  p25 {q.loc[0.25]:,.0f}  median {q.loc[0.50]:,.0f}")

    return debt


def build_euro_score(client: FiscalDataClient, *, keep_raw: bool) -> pd.DataFrame:
    """Quantity-only Duration Shift Score for Germany, France and Italy.

    Three of the six factors, quarterly, one score per country. No WAM, no term
    premium, no auction stress — not because they were dropped but because no free
    source publishes them for these sovereigns. The variant travels on every row so
    a quantity-only 70 can never be read as though it were a full-score 70.

    NO REGIME is assigned. The regime classifier caps a high score using
    market-price corroboration, and there is none here; a regime derived from the
    band alone would be the score wearing a second name and would imply the market
    evidence had been checked and agreed. The band is published, the regime is not.

    NO CASH ADJUSTMENT either. Deviation D5 removes the debt-ceiling cash rebuild
    from the US funding ratio. These sovereigns have no debt ceiling, but they do
    have their own cash-management distortions, and whether an equivalent
    correction is needed is an open question rather than a settled no
    (docs/phase3_source_assessment.md).
    """
    source = PROCESSED / "euro_debt.parquet"
    if not source.exists():
        raise FileNotFoundError(
            "the euro score needs euro_debt.parquet; run "
            "`python scripts/refresh.py --only euro_debt` first"
        )

    debt = pd.read_parquet(source)
    thresholds = _thresholds()
    weights_cfg = yaml.safe_load(
        (REPO_ROOT / "config" / "factor_weights.yaml").read_text(encoding="utf-8")
    )
    weighting = weights_cfg["weighting"]
    pct_cfg = thresholds["percentiles"]
    floors = thresholds["issuance"]["min_abs_denominator_quarterly_meur"]

    # Coupons here are the single F32 long-term class, not the US list of NOTES /
    # BONDS / FRN. Passing the US names would silently aggregate nothing and make
    # coupon restraint NaN for every quarter while the score still published on the
    # two remaining factors.
    coupon_classes = ("COUPONS",)

    frames = []
    for country in sorted(debt["country"].unique()):
        variant_name, variant = resolve_variant(country, weights_cfg)
        one = debt[debt["country"] == country].copy()

        if country not in floors:
            raise KeyError(
                f"no quarterly ratio floor calibrated for {country!r}; add it to "
                "issuance.min_abs_denominator_quarterly_meur with the observed "
                "distribution recorded next to it"
            )
        floor = float(floors[country]) * MILLIONS

        share = bill_share(one, freq="Q")
        net = net_issuance(one, freq="Q")
        funding = incremental_bill_funding(
            net, coupon_classes=coupon_classes, min_abs_denominator=floor
        )["incremental_bill_funding"]

        # horizon=4: four quarters is the year that horizon=12 means monthly.
        factors = build_factors(
            bill_share_series=share,
            net=net,
            incremental_funding=funding,
            coupon_classes=coupon_classes,
            min_abs_denominator=floor,
            horizon=4,
        )[variant["factors"]]

        ranks = percentile_ranks(
            factors,
            window=pct_cfg["window_quarters"],
            min_periods=pct_cfg["min_history_quarters"],
        )
        weights = expanding_weights(
            ranks,
            ridge=float(weighting["ridge"]),
            min_months=int(weighting["min_quarters_for_weights"]),
        )
        scored = duration_shift_score(
            ranks, weights,
            min_factors=int(variant["min_factors"]),
            variant=variant_name,
        )
        scored["band"] = score_band(
            scored["score"], thresholds["duration_shift_score_bands"]["bands"]
        )
        for name in ranks.columns:
            scored[f"rank_{name}"] = ranks[name]
            scored[f"weight_{name}"] = weights[name]

        out = scored.reset_index().rename(columns={"index": "period"})
        out["period"] = out["period"].astype(str)
        out["country"] = country
        out["frequency"] = "Q"
        out["total_is_derived"] = True
        frames.append(out)

        live = scored["score"].dropna()
        masked = int(funding.isna().sum())
        if len(live):
            print(f"    {country} [{variant_name}]: score {live.iloc[-1]:.1f} at "
                  f"{live.index[-1]} ({scored.loc[live.index[-1], 'band']}), "
                  f"{len(live)} scored quarters from {live.index[0]}")
        else:
            print(f"    {country} [{variant_name}]: no scored quarters")
        # min_factors is 3 of 3, so a masked funding ratio does not degrade the
        # score, it removes it. That is the intended behaviour — a two-factor
        # reading is a third measurement, not a weaker version of this one — but
        # it is also the main reason the series has holes, so it is reported.
        print(f"      bill share {share.iloc[-1]:.1%}, "
              f"4q change {share.diff(4).iloc[-1]:+.2%}, "
              f"funding ratio masked in {masked} of {len(funding)} quarters "
              f"(floor €{floor/1e6:,.0f}mn); a masked quarter has no score")

        # A score that moves against its most legible input is the shape a sign
        # error takes, and this project has shipped one. The latest quarter's raw
        # factor value, its point-in-time rank and its weight are printed so a
        # reading can be checked against its parts rather than trusted.
        if len(live):
            at = live.index[-1]
            window = int(pct_cfg["window_quarters"])
            for name in ranks.columns:
                print(f"      {name:<26} raw {factors.loc[at, name]:>9.4f}  "
                      f"rank {ranks.loc[at, name]:>5.2f}  "
                      f"weight {weights.loc[at, name]:>5.2f}  "
                      f"contributes {scored.loc[at, f'contrib_{name}']:>5.1f}")
                # A percentile rank measures a reading against the country's OWN
                # recent behaviour, so a rank above 50 on a falling bill share is
                # not necessarily wrong — it can mean "falling less than usual".
                # The trailing distribution the rank was taken against is printed
                # so that reading can be checked instead of argued about.
                trailing = factors[name].loc[:at].tail(window).dropna()
                if len(trailing) > 1:
                    d = trailing.quantile([0, 0.25, 0.5, 0.75, 1.0])
                    negative = float((trailing < 0).mean())
                    print(f"        trailing {len(trailing)}q: "
                          f"min {d.iloc[0]:+.4f}  p25 {d.iloc[1]:+.4f}  "
                          f"med {d.iloc[2]:+.4f}  p75 {d.iloc[3]:+.4f}  "
                          f"max {d.iloc[4]:+.4f}  ({negative:.0%} negative)")

    combined = pd.concat(frames, ignore_index=True)
    combined["retrieval_date"] = pd.Timestamp.now("UTC")

    # The variant is what stops these numbers being read against the US score, so
    # its absence is a data-integrity failure rather than a cosmetic one.
    if combined["variant"].isna().any():
        raise ValueError("scored rows are missing the variant label")

    # No quality event is recorded for the narrowness of this variant. The quality
    # log's event types are a closed vocabulary of things that went WRONG with a
    # feed, and a quantity-only score is not a defect — it is the measurement.
    # What stops it being misread is the `variant` column on every row, which is a
    # stronger guarantee than a log line anyone can fail to read.
    return combined


def build_score(client: FiscalDataClient, *, keep_raw: bool) -> pd.DataFrame:
    """Fiscal Duration Shift Score, from tables the other builders produced.

    Reads the processed store rather than the API — every input is already
    validated, and recomputing them here would let the score drift away from what
    the pages display.
    """
    needed = ["debt_outstanding", "wam", "term_premium", "long_end_stress", "cash_balance"]
    missing = [n for n in needed if not (PROCESSED / f"{n}.parquet").exists()]
    if missing:
        raise FileNotFoundError(
            f"the score needs {missing}; run those builders first "
            f"(python scripts/refresh.py --only {missing[0]})"
        )

    read = {n: pd.read_parquet(PROCESSED / f"{n}.parquet") for n in needed}
    thresholds = _thresholds()
    weights_cfg = yaml.safe_load(
        (REPO_ROOT / "config" / "factor_weights.yaml").read_text(encoding="utf-8")
    )["weighting"]
    floor = float(thresholds["issuance"]["min_abs_denominator_monthly_musd"]) * 1_000_000
    coupon_classes = tuple(thresholds["issuance"]["coupon_classes"])

    debt = read["debt_outstanding"]
    net = net_issuance(debt)

    wam_years = read["wam"].set_index(
        pd.PeriodIndex(pd.to_datetime(read["wam"].observation_date), freq="M")
    )["wam_years"]

    tp = read["term_premium"]
    tp10 = tp[tp["maturity"].astype(str) == "10Y"].set_index("date")["value"].sort_index()
    tp10 = tp10.resample("ME").last()
    tp10.index = tp10.index.to_period("M")

    stress = read["long_end_stress"].set_index("date")["long_end_stress"].sort_index()
    stress = stress.resample("ME").last()
    stress.index = stress.index.to_period("M")

    cash = month_end_cash_balance(read["cash_balance"])

    # Deviation D5. The cash-adjusted ratio is the published one: borrowing that
    # rebuilt the Treasury General Account after a debt-ceiling episode did not
    # finance a deficit, and counting it as duration shortening is the most likely
    # false positive here. The unadjusted ratio is kept alongside, because it is
    # what actually happened to the debt stock.
    adjusted = thresholds["debt_ceiling_episodes"].get("cash_adjustment", True)
    unadj = incremental_bill_funding(net, min_abs_denominator=floor)[
        "incremental_bill_funding"
    ]
    adj = cash_adjusted_bill_funding(net, cash, min_abs_denominator=floor)[
        "incremental_bill_funding_adjusted"
    ]
    funding = adj if adjusted else unadj
    print(f"    incremental bill funding: {'cash-adjusted' if adjusted else 'unadjusted'}")

    factors = build_factors(
        bill_share_series=bill_share(debt),
        net=net,
        incremental_funding=funding,
        wam_years=wam_years,
        term_premium_10y=tp10,
        auction_stress=stress,
        coupon_classes=coupon_classes,
        min_abs_denominator=floor,
    )

    pct_cfg = thresholds["percentiles"]
    ranks = percentile_ranks(
        factors, window=pct_cfg["window_months"], min_periods=pct_cfg["min_history_months"]
    )
    weights = expanding_weights(
        ranks, ridge=float(weights_cfg["ridge"]),
        min_months=int(weights_cfg["min_months_for_weights"]),
    )
    scored = duration_shift_score(
        ranks, weights, min_factors=int(weights_cfg["min_factors"])
    )
    scored["band"] = score_band(
        scored["score"], thresholds["duration_shift_score_bands"]["bands"]
    )

    # Corroboration thresholds are percentiles of each input's own point-in-time
    # history, so they are calibrated rather than guessed and cannot be silently
    # unreachable. Supplied explicitly; a condition naming an absent input raises.
    corroboration = percentile_ranks(
        pd.DataFrame({
            "bill_share_12m_change": bill_share(debt).diff(12),
            "long_end_auction_stress": stress,
        }),
        window=pct_cfg["window_months"], min_periods=pct_cfg["min_history_months"],
    )
    regime_inputs = pd.DataFrame({
        "duration_shift_score": scored["score"],
        "term_premium_10y_percentile": ranks["term_premium_10y_trend"],
        "bill_share_12m_change_percentile": corroboration["bill_share_12m_change"],
        "long_end_auction_stress_percentile": corroboration["long_end_auction_stress"],
    })
    scored["regime"] = classify_regime(regime_inputs, thresholds["regimes"])

    for name in ranks.columns:
        scored[f"rank_{name}"] = ranks[name]
        scored[f"weight_{name}"] = weights[name]

    out = scored.reset_index().rename(columns={"index": "period"})
    out["period"] = out["period"].astype(str)
    out["country"] = "US"
    out["cash_adjusted"] = adjusted
    out["retrieval_date"] = pd.Timestamp.now("UTC")

    # The regime conditions in config do not partition the score range: a month
    # with a score of 55 and a bill-share change below the yellow threshold
    # satisfies neither green (which requires < 40) nor yellow. That is a config
    # design gap, so it is counted and surfaced rather than filled with a default
    # regime nobody chose.
    unclassified = int(scored["score"].notna().sum() - scored["regime"].notna().sum())
    if unclassified:
        share = unclassified / max(int(scored["score"].notna().sum()), 1)
        detail = (
            f"{unclassified} scored months ({share:.0%}) match no regime. The "
            "conditions in thresholds.yaml do not cover the whole score range — "
            "green_normal requires a score below 40 while yellow_shortening "
            "requires 40 or above AND a bill-share condition, so readings in "
            "between fall through. Needs a config decision, not a default."
        )
        print(f"    note: {detail}")
        QUALITY_NOTES.append(
            {"source": "score", "endpoint": "duration_shift_score",
             "event_type": "contract_break", "severity": "warning", "detail": detail}
        )

    live = scored["score"].dropna()
    if len(live):
        last = live.index[-1]
        print(f"    score {live.iloc[-1]:.1f} at {last} "
              f"({scored.loc[last, 'band']}, regime {scored.loc[last, 'regime']})")
        print(f"    {len(live)} scored months, {live.index[0]} → {last}")
    return out


BUILDERS = {
    "debt_outstanding": build_debt_outstanding,
    "cash_balance": build_cash_balance,
    "auctions": build_auctions,
    "wam": build_wam,
    "term_premium": build_term_premium,
    "rates": build_rates,
    "euro_debt": build_euro_debt,
    # After euro_debt: it reads what that builder wrote.
    "euro_score": build_euro_score,
    # Last: it reads what the others wrote.
    "score": build_score,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", choices=sorted(BUILDERS), action="append")
    ap.add_argument("--no-raw", action="store_true", help="skip the raw archive")
    args = ap.parse_args()

    wanted = args.only or sorted(BUILDERS)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    client = FiscalDataClient()

    failures: list[str] = []
    quality = QualityLog()
    staleness_cfg = _thresholds()["validation"]["staleness_days"]
    built: dict[str, pd.DataFrame] = {}

    for name in wanted:
        print(f"\n{name}:")
        try:
            table = BUILDERS[name](client, keep_raw=not args.no_raw)
        except MissingCredential as exc:  # noqa: PERF203
            # A configuration gap, not a broken feed. Still a failure — a refresh
            # that quietly skipped a source would leave a stale table looking current.
            print(f"    SKIPPED: {exc}", file=sys.stderr)
            failures.append(f"{name}: no credential")
            quality.record(source=name, endpoint=name, event_type="fetch_failure",
                           severity="error", detail=f"missing credential: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - the point is to fail loudly
            print(f"    FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            failures.append(f"{name}: {type(exc).__name__}")
            kind = ("contract_break" if "Contract" in type(exc).__name__
                    else "reconciliation_break" if "reconcil" in str(exc).lower()
                    else "fetch_failure")
            quality.record(source=name, endpoint=name, event_type=kind,
                           severity="error", detail=f"{type(exc).__name__}: {exc}")
            continue

        # Written only after its checks have passed, so a half-finished refresh
        # cannot leave a plausible-but-wrong file behind.
        target = PROCESSED / f"{name}.parquet"
        table.to_parquet(target, index=False)
        built[name] = table
        print(f"    processed → {target.relative_to(REPO_ROOT)}")

    # Staleness is judged against the latest OBSERVATION, not the retrieval time:
    # a feed fetched successfully every morning that has published nothing for a
    # month is stale, and a check on retrieval would call it healthy.
    date_columns = {"debt_outstanding": ("observation_date", "mspd"),
                    "wam": ("observation_date", "mspd"),
                    "term_premium": ("date", "nyfed_acm"),
                    "auctions": ("auction_date", "auctions"),
                    "rates": ("date", "fred_daily"),
                    "euro_debt": ("observation_date", "eurostat_quarterly")}
    for name, table in built.items():
        column, threshold_key = date_columns.get(name, (None, None))
        if column is None or column not in table.columns:
            continue
        event = check_staleness(
            pd.to_datetime(table[column]).max(),
            source=name, endpoint=name,
            max_age_days=staleness_cfg[threshold_key],
        )
        if event:
            print(f"  STALE {name}: {event['detail']}", file=sys.stderr)
            quality.record(**event)
            failures.append(f"{name}: stale")

    for note in QUALITY_NOTES:
        quality.record(**note)

    events = quality.to_frame()
    events.to_parquet(PROCESSED / "data_quality_events.parquet", index=False)
    print(f"\n{len(events)} data quality event(s) → "
          f"data/processed/data_quality_events.parquet")

    if failures:
        print(f"\n{len(failures)} source(s) failed:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("\nRefresh complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
