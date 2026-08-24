# Sovereign Debt Duration & Fiscal Liquidity Monitor

Measures whether the marginal fiscal deficit is being financed with **bills instead
of duration**, and whether the sovereign is deliberately shortening its financing
profile. Level of debt is context; direction of travel is the signal.

**A conditions monitor, not a forecasting tool.** The project's own backtest found
no reliable forward information in its signals (see
[`docs/backtest.md`](docs/backtest.md)), and every surface says so. What it does
instead is measure the financing profile to a fiduciary-defensible standard and
escalate only when the market observably corroborates — a design the backtest
justifies rather than embarrasses.

Free official data only — Treasury Fiscal Data, FRED, NY Fed, Eurostat. No paid
vendors. The one credential is a FRED API key (`FRED_API_KEY`), used by ingestion
only: the dashboard reads `data/processed/` and never calls an API at page load.

```bash
python scripts/refresh.py     # pull → normalize → validate → data/processed/
streamlit run app/Home.py
python -m pytest tests/ -q    # 351 tests
```

## Status: complete

Phases 1–2 are built and validated; Phase 3 is built as far as free structured
sources exist. The system maintains itself: a weekday refresh that fails loudly, a
weekly source-contract probe, and a standing drift check of our WAM against
Treasury's own published series. Remaining items are parked with written re-entry
conditions, not pending.

Readings as at the latest refresh (2026-07 stock data, 2026-08 operations):

| metric | reading |
|---|---|
| Bill share of marketable | **22.2%** (+1.5pp / 1y), above TBAC's 15–20% band — verified against the committee's own minutes |
| Fiscal Duration Shift Score | **54.5** · neutral · regime `yellow_shortening`, corroboration complete |
| Weighted average maturity | **5.82y** (69.8 months), −0.16y / 1y — reconciles with Treasury's published series to a median of 0.01 months over 306 months |
| 10y term premium (ACM) | **0.82%** |
| Long-end auction stress | **−10.7** (negative = better absorbed than trailing average) |
| Euro area (quantity-only variant) | DE **53.8**, FR **63.4**, IT **52.3** (2026-Q1) — not comparable to the US score, and the app enforces that |
| Buyback operations ingested | 217 since 2000, $519bn par — and adjusted out of the score |

## What is validated, and how

Every number traces to an official source. `config/` marks each claim as one of
three kinds — `verified` (a fact confirmed against a source), `calibrated` (a
threshold set from the observed distribution, evidence alongside), or
`convention` (an interpretive choice, declared) — and a test refuses config
blocks that don't say which they are.

- **Source contract.** Every endpoint and field in
  [`config/sources.yaml`](config/sources.yaml) was observed in a live response;
  the weekly probe re-verifies and commits evidence to `docs/source_probe/`.
- **WAM, externally.** Computed independently from CUSIP-level detail, it matches
  Treasury's published *Average Maturity of Total Outstanding* to +0.01 months
  median over 2001–2026. The known 2001–2007 divergence (+2.7 months) is priced —
  ~40% is the callable-bond convention, measured and deliberately not modelled —
  and a weekly check fails if the modern period drifts past half a month
  ([`docs/wam_reconciliation.md`](docs/wam_reconciliation.md)).
- **TBAC 15–20% band.** Cited to twelve sets of the committee's own minutes,
  fetched from Treasury; the two *other* TBAC ranges (25–33% of new issuance,
  30–35% short-period tolerance) are recorded so they can never be conflated.
- **Mechanical distortions are corrected from official series, not assumptions.**
  The debt-ceiling TGA rebuild (episodes detected from Debt to the Penny) and
  buyback retirements (from the buybacks dataset) are both removed from the
  funding ratios; each would otherwise read as strategic shortening.

## What the backtest established

([`docs/backtest.md`](docs/backtest.md); circular block bootstrap, all 48 tests
counted, signals restricted to quantity factors so the score's own inputs can't
predict themselves.)

- Quantity signals lead **one estimate** of the 10y term premium (ACM) at 3–6
  months, IC ≈ 0.25 — and the same test against Kim-Wright returns ≈ 0.11 and
  does not clear zero. **Model-dependent; not established.**
- Quantity signals show **no forward relationship to long-end auction stress**.
  Twelve tests, none distinguishable from zero.
- Hence the framing above, and the regime design: quantity evidence alone can
  reach `yellow`; `orange`/`red` require the market to corroborate *now*. The
  score also carries `regime_evidence`, distinguishing "the market disagreed"
  from "the corroborating series didn't exist yet" (it didn't, before 2013).

## Two speeds

The stock data (MSPD) is monthly, published ~4 business days after month-end —
**structurally 3–7 weeks behind, always**. Auction results, buyback operations,
the TGA and the term premium are days old. The Operations page carries what
Treasury executed this week; Treasury's forward intentions are announced
(refunding, auction and buyback schedules), not inferred.

## App

| page | shows |
|---|---|
| Home | KPI row, bill share vs TBAC band, issuance mix, WAM, score, interaction flag |
| Operations | executed buybacks and auctions, days old |
| Auctions | per-auction stress with rolling stats |
| Issuance | bill share, net issuance by class, funding ratios |
| Term premium | ACM with revision tracking, Kim-Wright cross-check, curve spreads |
| Fiscal & liquidity | interest expense ratios, TGA, RRP, reserves |
| QRA input | manual refunding log; first row is the Nov-2023 coupon-restraint episode, every figure cited |
| Data quality | staleness, contract breaks, revisions, reconciliation events |
| Cross-country | DE/FR/IT quantity-only scores, absolute direction beside every reading |
| Methodology | rendered from `docs/`, opens with what this monitor can and cannot claim |

## Parked, with re-entry conditions

- **UK / Japan** — no structured endpoint found (DMO/MOF serve HTML); recorded in
  [`docs/phase3_source_assessment.md`](docs/phase3_source_assessment.md).
- **Euro interpretation bands** — withdrawn: extreme readings don't mark episodes
  the way the US bands' do. Three restoration conditions documented in
  [`docs/euro_band_backtest.md`](docs/euro_band_backtest.md).
- **Pre-2008 WAM residual** (~1.6 months) and the **ACM/Kim-Wright ambiguity** —
  both need data that isn't free (prospectus call schedules; point-in-time ACM
  vintages). Documented, not chased.
- **Phase 4 asset overlay** — unstarted by choice: a forward-returns overlay on a
  score with no demonstrated forward information needs its own careful framing.

## Principles

Never fabricate data. Never interpolate silently — missing stays visibly missing
with a quality flag. Never substitute an unofficial source where an official one
exists. Every assumption lives in `config/`, marked for what kind of claim it is.
And the standard applies to the thesis too: the backtest that weakened it is
published with the same prominence as the measurements that support it.
