# Data dictionary

All amounts in the processed store are in **single currency units** unless the
column says otherwise. The source publishes MSPD in millions and Debt to the
Penny in whole dollars; conversion happens once, at ingestion.

## `debt_outstanding`

| column | type | notes |
|---|---|---|
| `observation_date` | date | MSPD month end |
| `publication_date` | date | Always empty — not carried by the endpoint, not estimated (D4) |
| `country` | category | `US` |
| `security_class` | category | `BILLS, NOTES, BONDS, TIPS, FRN, OTHER, TOTAL_MARKETABLE` |
| `amount_outstanding` | float | Single currency units |
| `amount_basis` | category | `PAR`, or `INFLATION_ADJUSTED` for TIPS |
| `currency` | category | `USD` |
| `source`, `retrieval_date` | str, timestamp | Provenance |

`TOTAL_MARKETABLE` is the published row, never a sum of the parts. `OTHER` is
Federal Financing Bank. TIPS before 2004-06 are the sum of the two
inflation-indexed rows Treasury published then.

## `securities_detail` (latest snapshot only)

`observation_date, cusip, security_class, issue_date, maturity_date,
amount_outstanding, accretion, amount_par, interest_rate, amount_basis, country,
currency, source, retrieval_date`

One row per (date, CUSIP). `amount_outstanding` is as published — inflation
adjusted for TIPS. `amount_par` = outstanding − accretion, with accretion summed
across the security's tranches. Full history stays in `data/raw` (D7).

## `wam`

`observation_date, wam_years, amount_outstanding, within_1y, within_2y,
within_3y, within_5y, amount_basis, country, source, retrieval_date`

Buckets are cumulative and inclusive: `within_2y` contains `within_1y`.

## `auctions`

`auction_date, issue_date, maturity_date, country, security_type, term, cusip,
amount_offered, amount_accepted, amount_accepted_competitive, soma_add_on,
bid_to_cover, high_yield, median_yield, primary_dealer_pct, direct_pct,
indirect_pct, allotment_at_high_pct, dispersion_bps, tail_proxy_bps,
tail_proxy_method, has_results, bidder_share_basis, stress_score, ...`

`term` is the CANONICAL tenor from the original security term, not the remaining
term. Bidder shares are fractions of competitive accepted. `has_results` is False
for auctions held before results were published (all of the 1980s).

## `term_premium`

`date, country, maturity, model, value, units, vintage_date, retrieval_date,
revision_flag`

Daily, from 1991 in the processed store. `revision_flag` marks values that
changed against the prior vintage.

## `rates`

`date, series_id, value, frequency, units, seasonal_adjustment, source,
retrieval_date`

**Units differ between series and so does seasonal adjustment.** `RRPONTSYD` is
billions while `WALCL`, `WRESBAL` and `WTREGEN` are millions. `GDP`, `FGRECPT`
and `A091RC1Q027SBEA` are SAAR; everything else is NSA. Both are carried per row
so no consumer can mix them silently.

## `data_quality_events`

`event_date, source, endpoint, event_type, severity, detail, retrieval_date`

`event_type` ∈ `fetch_failure, contract_break, staleness, parse_failure,
revision, reconciliation_break`. `severity` ∈ `info, warning, error`.

## `qra_log` (manual)

As entered from the official Treasury documents. Amounts are in **billions**, the
unit the QRA states them in. `source_url` is mandatory and validated non-empty.

## `cash_balance`

Daily Treasury General Account balance (Deviation D5's input).

| column | meaning |
|---|---|
| `date` | business day |
| `balance` | closing TGA balance, USD |
| `country`, `currency`, `source`, `retrieval_date` | provenance |

## `long_end_stress`

Rolling long-end auction stress across 10/20/30Y auctions.

| column | meaning |
|---|---|
| `date` | as-of date |
| `long_end_stress` | rolling composite; negative = better absorbed than trailing average |
| `country` | `US` |

## `score`

The Fiscal Duration Shift Score, monthly, with everything needed to explain a
reading. One row per month.

| column | meaning |
|---|---|
| `period` | month, `YYYY-MM` |
| `score` | 0–100 composite; NaN below `min_factors` available factors |
| `n_factors` | factors available that month |
| `rank_*` / `weight_*` / `contrib_*` | per-factor point-in-time percentile, expanding correlation-adjusted weight, and contribution to the score |
| `band` | interpretation band from config (US bands, `validated_for_variants`) |
| `regime` | quantitative regime, corroboration-gated escalation |
| `regime_evidence` | `complete`, or `incomplete: <inputs>` — a regime capped by an input that DID NOT EXIST is not the same finding as one the market argued against |
| `cash_adjusted` | whether incremental bill funding removed the TGA change (D5) |

The score is also buyback-adjusted (par retired is added back to the coupon
flow); see `buybacks`.

## `euro_debt`

Eurostat `gov_10q_ggdebt`, central government (S1311), quarterly, EUR.

| column | meaning |
|---|---|
| `security_class` | `BILLS` (F31), `COUPONS` (F32), `TOTAL_MARKETABLE` |
| `total_is_derived` | TRUE on total rows: Eurostat publishes no total, so it is the sum of the two classes and the US-style reconciliation check has nothing to test |
| others | as `debt_outstanding` |

## `euro_score`

Quantity-only Duration Shift Score for DE/FR/IT. **A different measurement from
the US score** — three factors, quarterly, no market-price evidence — and never
comparable with it; `variant` travels on every row and the app enforces
`comparable_with`.

| column | meaning |
|---|---|
| `variant` | `quantity_only` |
| `band` | always null: the US bands are not validated for this variant (`docs/euro_band_backtest.md`) |
| `bill_share`, `bill_share_4q_change`, `direction_absolute` | the ABSOLUTE reading beside the relative score — the score is a percentile of the country's own history and can read high while the bill share falls |
| `score_is_relative_to_own_history` | always TRUE, as a machine-readable warning |
| others | as `score`, reduced to the three quantity factors |

## `buybacks`

Treasury buyback operations, one row each, 2000-03 onward. Feeds the buyback
adjustment: MSPD deltas net retired securities into "issuance", so an
unadjusted coupon buyback reads as strategic coupon restraint when it is an
announced operation.

| column | meaning |
|---|---|
| `operation_date`, `settlement_date` | operation timing |
| `operation_type` | `Liquidity Support`, `Cash Management`, `Small Value`; missing on the 2000–02 program |
| `security_class` | `COUPONS` or `TIPS` |
| `class_assumed` | TRUE where the source stated no type (the 2000–02 program, mapped to COUPONS) |
| `total_par_amt_offered`, `par_accepted`, `max_par_amt_redeemed` | USD |

No staleness threshold, deliberately: the programs have year-long gaps between
them, and a paused program is policy, not a broken feed.

## `buybacks_security_details`

CUSIP-level buyback results — which securities were bought, at what par and
price. `par_amt_accepted` is 0 for eligible-but-not-purchased securities. Not
used by the adjustment (the factors consume coupons as an aggregate); kept for
the Operations page and future attribution.

## `qra_log` — first entry

The Nov-2023 row (the coupon-restraint episode) is entered: borrowing estimates
and cash balances read from the fetched Q4-2023 Treasury OFP materials
(verbatim passages under `docs/source_probe/qra/`), auction size changes
computed from our own `auctions` table, commentary quoted verbatim. Fields the
evidence did not support unambiguously are left empty rather than filled.
