# Sovereign Debt Duration & Fiscal Liquidity Monitor

Tracks whether the marginal fiscal deficit is being financed with **bills instead of
duration**, and whether the sovereign is deliberately shortening its financing profile.
Level of debt is context; direction of travel is the signal.

Free official data only — Treasury Fiscal Data, FRED, NY Fed. No paid vendors. The one
credential is a FRED API key, supplied via `FRED_API_KEY` or Streamlit secrets.

## Status

**Pre-build.** Plan proposed, awaiting approval. No ingestion, calculation or app code yet.

Blocking item: the four data-source hosts are refused by this environment's network egress
policy, so live field names could not be verified. Field mappings are therefore declared as a
machine-checked contract rather than written from memory.

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
