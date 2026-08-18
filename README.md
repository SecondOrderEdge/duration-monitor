# Sovereign Debt Duration & Fiscal Liquidity Monitor

Tracks whether the marginal fiscal deficit is being financed with **bills instead of
duration**, and whether the sovereign is deliberately shortening its financing profile.
Level of debt is context; direction of travel is the signal.

Free official data only — Treasury Fiscal Data, FRED, NY Fed. No paid vendors. The one
credential is a FRED API key, read from `FRED_API_KEY`. It belongs to ingestion, not to
the app: the dashboard reads `data/processed/` and never calls an API, so it needs no
credential at all.

## Status

**Phase 1: the dashboard renders live data.** Bill share and net issuance are built
end-to-end from Treasury Fiscal Data and reconciled against the published totals.
WAM, term premium and auction stress have tested calculations but no ingestion yet,
and are shown on the dashboard as explicitly unavailable rather than blank.

```bash
python scripts/refresh.py     # pull → normalize → validate → data/processed/
streamlit run app/Home.py     # reads data/processed/ only; no API calls at page load
```

Every source is verified against live responses; evidence is committed under
`docs/source_probe/`. The FRED probe runs in GitHub Actions, the only place it can:
FRED is the one credentialed source and the key lives in repository secrets.

What the current data says: bill share is **22.2%** as at 2026-07, above the 15–20%
band TBAC has long referenced, and up 1.5pp over twelve months.

### Build sequence

| step | state |
|---|---|
| 0 · probe sources, correct the contract | done — all 8 fiscaldata endpoints, FRED, NY Fed |
| 1 · typed parsing + fiscaldata client | done |
| 2 · MSPD Table 1 → `debt_outstanding` | done — reconciles to 3e-5% |
| 3 · bill share, net issuance, funding ratios | done, on the dashboard |
| 4 · `securities_detail` → WAM | calculations done, ingestion not written |
| 5 · FRED + NY Fed ACM ingestion | not written |
| 6 · auctions ingestion + stress score | calculations done, ingestion not written |
| 7 · validation + `data_quality_events` | reconciliation done, rest not written |
| 8 · Streamlit subpages | Home only |
| 9 · QRA input, data quality, methodology pages | not written |
| 10 · scheduled refresh workflow | not written |

| module | covers |
|---|---|
| `src/ingestion/typed.py` | declared per-field coercion; `"null"` → NaN with failure counting |
| `src/ingestion/fiscaldata.py` | paginating, retrying client; contract and completeness enforcement |
| `src/transformation/normalize.py` | raw → `debt_outstanding`; class renames, units, TIPS basis |
| `src/validation/reconciliation.py` | components vs the published marketable total |
| `src/calculations/timegrid.py` | period-aware changes; missing months never closed up |
| `src/calculations/percentiles.py` | point-in-time percentile ranks and trailing z-scores |
| `src/calculations/wam.py` | weighted average maturity, maturity buckets |
| `src/calculations/issuance.py` | bill share, net issuance, funding ratios and their guards |
| `src/signals/auction_stress.py` | per-auction stress score, long-end rolling stress |
| `app/Home.py` | KPI row, bill share, quarterly net issuance |

```bash
python -m pytest tests/ -q      # 157 tests
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
