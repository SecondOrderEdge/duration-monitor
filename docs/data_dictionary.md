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
