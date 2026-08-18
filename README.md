# Sovereign Debt Duration & Fiscal Liquidity Monitor

Tracks whether the marginal fiscal deficit is being financed with **bills instead of
duration**, and whether the sovereign is deliberately shortening its financing profile.
Level of debt is context; direction of travel is the signal.

Free official data only — Treasury Fiscal Data, FRED, NY Fed. No paid vendors. The one
credential is a FRED API key, read from `FRED_API_KEY`. It belongs to ingestion, not to
the app: the dashboard reads `data/processed/` and never calls an API, so it needs no
credential at all.

## Status

**Phase 1: six of eight headline metrics render from live official data.** Bill
share, incremental bill funding, WAM, the 10y ACM term premium and long-end auction
stress are all built end-to-end and reconciled against published figures. The two
remaining cards are the Phase 2 composite score and the Phase 3 global score.

```bash
python scripts/refresh.py     # pull → normalize → validate → data/processed/
streamlit run app/Home.py     # reads data/processed/ only; no API calls at page load
```

Every source is verified against live responses; evidence is committed under
`docs/source_probe/`. The FRED probe runs in GitHub Actions, the only place it can:
FRED is the one credentialed source and the key lives in repository secrets.

What the data currently says, as at 2026-07:

| metric | reading |
|---|---|
| Bill share of marketable | **22.2%**, above the 15–20% band TBAC references |
| 1y change in bill share | **+1.5pp** |
| Incremental bill funding | **78%** of net marketable borrowing |
| Weighted average maturity | **5.82y**, −0.16y over twelve months |
| 10y term premium (ACM) | **0.89%**, +0.12pp over twelve months |
| Long-end auction stress | **−10** (negative = better absorbed than trailing average) |

### Build sequence

| step | state |
|---|---|
| 0 · probe sources, correct the contract | done — all 8 fiscaldata endpoints, 21 FRED series, NY Fed |
| 1 · typed parsing + fiscaldata client | done |
| 2 · MSPD Table 1 → `debt_outstanding` | done — reconciles to 3e-5% |
| 3 · bill share, net issuance, funding ratios | done, on the dashboard |
| 4 · `securities_detail` → WAM | done — 5.82y, matches Treasury's published average length |
| 5 · FRED + NY Fed ACM ingestion | done — ACM live; FRED client written, needs the key |
| 6 · auctions ingestion + stress score | done — 11,078 auctions from 1979, scored from 2008-04 |
| 7 · validation + `data_quality_events` | reconciliation and revision detection done; event table not written |
| 8 · Streamlit subpages | Home only |
| 9 · QRA input, data quality, methodology pages | not written |
| 10 · scheduled refresh workflow | not written |

| module | covers |
|---|---|
| `src/ingestion/typed.py` | declared per-field coercion; `"null"` → NaN with failure counting |
| `src/ingestion/fiscaldata.py` | paginating, retrying client; contract and completeness enforcement |
| `src/ingestion/fred.py` | FRED observations; credential scrubbing, `"."` gap handling |
| `src/ingestion/nyfed.py` | ACM workbook; sheet pinning, date format, revision detection |
| `src/transformation/normalize.py` | raw → `debt_outstanding`, `securities_detail`, `auctions` |
| `src/validation/reconciliation.py` | components vs the published marketable total |
| `src/calculations/timegrid.py` | period-aware changes; missing months never closed up |
| `src/calculations/percentiles.py` | point-in-time percentile ranks and trailing z-scores |
| `src/calculations/wam.py` | weighted average maturity, maturity buckets |
| `src/calculations/issuance.py` | bill share, net issuance, funding ratios and their guards |
| `src/signals/auction_stress.py` | per-auction stress score, long-end rolling stress |
| `app/Home.py` | KPI row and five charts |

### Resolved deviations

- **D2** TIPS accretion is published separately, so net issuance is accretion-aware
  and par is recoverable rather than TIPS being dropped.
- **D3** Treasury publishes the median yield and allotment-at-high, so the stress
  score uses two genuine dispersion measures. The constant-maturity tail proxy the
  brief proposed stays at zero weight as a labelled diagnostic.
- **D9(b)** WAM is weighted at par, pinned in `config/thresholds.yaml`.
- Open Question 1 (WAM source) and Question 3 (auction history depth, 2008-04) are
  both closed on evidence.

```bash
python -m pytest tests/ -q      # 180 tests
```

- [`docs/implementation_plan.md`](docs/implementation_plan.md) — plan, schema, recommended
  deviations, open questions
- [`config/sources.yaml`](config/sources.yaml) — endpoint registry and field contract
  (everything `verified: false` until probed)
- [`scripts/probe_sources.py`](scripts/probe_sources.py) — verifies the contract against live
  responses

## Verifying sources

Run anywhere with network access; commit the evidence it writes.

```bash
pip install -r requirements.txt
export FRED_API_KEY=...          # optional; FRED probes skip cleanly without it
python scripts/probe_sources.py  # → docs/source_probe/<date>/, non-zero exit on contract break
```

## Principles

Never fabricate data. Never interpolate silently — missing stays visibly missing with a
quality flag. Never substitute an unofficial source where an official one exists. Every
published number traces to an official source, and every assumption lives in `config/`.
