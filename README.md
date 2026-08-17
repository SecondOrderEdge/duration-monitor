# Sovereign Debt Duration & Fiscal Liquidity Monitor

Tracks whether the marginal fiscal deficit is being financed with **bills instead of
duration**, and whether the sovereign is deliberately shortening its financing profile.
Level of debt is context; direction of travel is the signal.

Free official data only — Treasury Fiscal Data, FRED, NY Fed. No paid vendors. The one
credential is a FRED API key, supplied via `FRED_API_KEY` or Streamlit secrets.

## Status

**Phase 1: sources verified, calculation layer and fiscaldata client built and tested.**
Transformation, validation and the Streamlit app are not written yet.

The network block that stalled step 0 has cleared. Every Treasury Fiscal Data endpoint and
the NY Fed ACM file were probed live on 2026-08-17, `config/sources.yaml` was corrected
against what they actually return, and all eight endpoints now match their contract with no
field drift. Evidence is committed under `docs/source_probe/`.

Three questions the plan called load-bearing are answered, all favourably:

- **WAM is computable.** `mspd_table_3_market` carries `maturity_date` per security for the
  full 2001 → 2026 history, so no TreasuryDirect fallback is needed — which matters, as that
  host is the one still blocked.
- **TIPS accretion is separately published** as `inflation_adj_amt`, so net issuance can be
  accretion-adjusted rather than dropping TIPS (Deviation D2).
- **Auction dispersion is available** — `low_yield`, `avg_med_yield` and `allocation_pctage`
  — so the preferred high-minus-median and allotment-at-high measures are usable and the
  noisy CMT tail proxy stays a weight-0 diagnostic (Deviation D3).

Still open: `FRED_API_KEY` is not set anywhere the probe can see it, so FRED remains
`verified: false` — a credential gap, not a network one. MTS coverage starts 2015-03, not
2001, which constrains any factor built on the monthly deficit.

| module | covers |
|---|---|
| `src/ingestion/typed.py` | declared per-field coercion; `"null"` → NaN with failure counting |
| `src/ingestion/fiscaldata.py` | paginating, retrying API client; contract and completeness enforcement |
| `src/calculations/timegrid.py` | period-aware changes; missing months never closed up |
| `src/calculations/percentiles.py` | point-in-time percentile ranks and trailing z-scores |
| `src/calculations/wam.py` | weighted average maturity, maturity buckets |
| `src/calculations/issuance.py` | bill share, net issuance, funding ratios and their guards |
| `src/signals/auction_stress.py` | per-auction stress score, long-end rolling stress |

```bash
python -m pytest tests/ -q      # 134 tests
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
