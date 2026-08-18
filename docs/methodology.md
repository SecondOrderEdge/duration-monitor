# Methodology

Every number here traces to an official source. Where a convention changes the
answer, the convention is stated and lives in `config/`, not in code.

## The question

Is the marginal deficit being financed with bills instead of duration, and is the
sovereign deliberately shortening its financing profile? Level of debt is
context; direction of travel is the signal.

## Sources

| Series | Source | Notes |
|---|---|---|
| Debt outstanding by class | Treasury Fiscal Data `mspd_table_1` | Monthly, 2001-01 onward |
| Security-level detail | Treasury Fiscal Data `mspd_table_3_market` | Drives WAM |
| Auctions | Treasury Fiscal Data `auctions_query` | 1979 onward; scored from 2008-04 |
| Term premium | NY Fed ACM workbook | Daily; processed store from 1991 |
| Rates, liquidity, fiscal | FRED | 21 series, verified units and frequency |
| QRA | Manual entry | No API exists |

Field names are a machine-checked contract in `config/sources.yaml`, verified
against live responses by `scripts/probe_sources.py`. Evidence is committed under
`docs/source_probe/`.

## Calculations

**Bill share** = Bills outstanding / the PUBLISHED Total Marketable row. The
denominator is never a sum of the component classes: keeping the published total
independent is what makes the reconciliation check meaningful.

**Net issuance** = period-over-period change in amount outstanding by class. This
approximates net issuance — MSPD deltas net issuance against redemptions and
reopenings within the period. Quarterly figures are the SUM of monthly flows, not
the change recomputed on a quarterly calendar. A period missing a month is left
blank rather than partially summed.

**Incremental bill funding** = net bills / (net bills + net coupons). TIPS are
excluded from the coupon aggregate because month-over-month change in TIPS
outstanding includes inflation accretion (see D2). Periods where the denominator
is below a configured floor are masked (see D5).

**WAM** = Σ(amount × years to maturity) / Σ(amount), marketable only, valued at
each snapshot's own date. Weighted at PAR: TIPS are published inflation-adjusted
and weighting on that basis would count accretion as duration. Par is recovered
as outstanding minus accretion, where accretion is summed across the security's
tranches — accretion is reported per tranche while outstanding is reported per
security, so subtracting them row-wise overstates par by up to 20%.

**Auction stress** — higher means weaker absorption. A weighted mean of signed
z-scores against the trailing twelve auctions of the SAME tenor: bid-to-cover
(low is weak), indirect share (low is weak), primary dealer takedown (high is
weak, dealers being the residual buyer), high-minus-median yield (wide is weak)
and allotment at the high (high is weak). Scaled so ±3 standard deviations map to
±100 and clipped, with the clip recorded.

Bidder shares divide by COMPETITIVE accepted, not total accepted. The total also
contains SOMA add-ons, which reached 37% of an auction in 2020-21; dividing by it
would depress dealer and indirect shares in exactly the QE years and read as
weakening private demand.

## Stated conventions

- **Percentiles used in any score are point-in-time**, computed on a trailing
  window as of each date, with a minimum history before publishing. A full-sample
  variant appears on charts labelled descriptive-only. Ranking a 2005 reading
  against data through 2026 would make a backtest look-ahead contaminated (D1).
- **Daily series are resampled to month end** to meet monthly series. Monthly data
  is never forward-filled onto a daily axis for signal purposes (D8).
- **WAM uses final maturity** for FRNs and TIPS; callables mature at final
  maturity; non-marketable debt is excluded (D9).
- **Auction scoring starts 2008-04**, the first auction with a bidder-class
  breakdown. Earlier auctions are ingested and kept, never scored on a reduced
  factor set as though it were the full one.

## What is deliberately not done

- Missing observations are never interpolated. Missing stays visibly missing.
- A figure that cannot be reconciled against its published total is not published.
- Publication dates are not estimated. MSPD for month end *M* is not public until
  roughly the eighth business day of *M+1*, but the endpoint does not carry that
  date, so the column is left empty rather than derived (D4).
- QRA PDFs are not NLP-extracted in Phase 1.
- No third-party source is substituted where an official one exists.

## Known limitations

- **ACM revisions.** The backtest uses today's ACM vintage for history, because
  point-in-time vintages are not freely available. Term premium history is
  therefore revised data used as if it were real-time. This cannot be fixed, only
  disclosed; `THREEFYTP10` (Kim-Wright) is an independent model cross-check (D11).
- **No true auction tail.** A true tail needs the 1pm when-issued yield, which is
  not free. The published high-minus-median spread and allotment-at-high are used
  instead — genuine official measures of the same thing. The constant-maturity
  proxy the brief proposed is retained at zero weight as a labelled diagnostic.
- **Debt-ceiling episodes distort every issuance ratio.** During a binding ceiling
  net borrowing approaches zero and the post-resolution bill surge is a mechanical
  TGA rebuild, not a strategic duration decision. It will read as maximum-strength
  thesis confirmation. Episodes are configured, flagged and shaded (D5).
- **MTS coverage starts 2015-03**, so any metric built on the monthly deficit
  cannot claim a pre-2015 history.
- **DGS20 is discontinued 1986-12-31 to 1993-10-01** — a verified 2,466-day hole.
  Never interpolate a 20-year point across it.
