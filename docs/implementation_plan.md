# Sovereign Debt Duration & Fiscal Liquidity Monitor — Implementation Plan

**Status:** awaiting approval. No Phase 1 ingestion, calculation or app code has been written yet.

This document is deliverable 1, 3 and 4 of the requested first deliverable. Deliverable 2
(sample API responses confirming field names) is **blocked** — see §2.

---

## 1. Scope recap

The system answers one question: *is the marginal deficit being financed with bills instead
of duration, and is the sovereign deliberately shortening its financing profile?* Level of
debt is context, not signal. Direction of travel is the signal.

Phase 1 delivers: ingestion (Treasury fiscal data, FRED, NY Fed ACM), a normalized parquet
store, the ten Phase 1 calculations, a US dashboard, QRA manual entry, a data-quality page,
tests and a scheduled refresh workflow. Phase 2+ is designed for but not built.

---

## 2. Deliverable 2 (live field verification) is blocked

Every data host is refused by this session's network egress policy:

| Host | Result |
|---|---|
| `api.fiscaldata.treasury.gov` | 403 at CONNECT — policy denial |
| `api.stlouisfed.org` / `fred.stlouisfed.org` | 403 at CONNECT — policy denial |
| `www.newyorkfed.org` | 403 at CONNECT — policy denial |
| `treasurydirect.gov` | 403 at CONNECT — policy denial |

Confirmed via both direct HTTPS and the fetch tool; `pypi.org` and `github.com` are
reachable, so this is a per-host allowlist, not a broken network. Only the environment
owner can change it (Claude Code on the web → environment network policy).

**I have not written down field names from memory, and none appear in this plan or in
`config/sources.yaml` as fact.** Doing so is precisely the failure mode this project
exists to avoid: a hardcoded column mapping that silently maps the wrong series is
indistinguishable from fabricated data once it reaches a chart.

Instead, the contract is explicit and machine-checked:

- `config/sources.yaml` lists every endpoint and its `expected_fields`, each flagged
  `verified: false`.
- `scripts/probe_sources.py` pulls a 2-row sample from every source, records the **actual**
  field names, `meta.dataTypes`, true coverage start/end and row counts, audits which fields
  really do return the string `"null"`, and reports every expectation as OK / MISSING /
  UNEXPECTED. It writes evidence to `docs/source_probe/<date>/` and exits non-zero on any
  contract break, so CI can gate on it.

**To unblock:** either allowlist the four hosts above and I re-run the probe here, or run
it anywhere with network access and commit the output:

```bash
pip install -r requirements.txt
export FRED_API_KEY=...          # optional; FRED probes skip cleanly without it
python scripts/probe_sources.py
git add docs/source_probe && git commit -m "probe: live source field evidence"
```

I will correct `sources.yaml` against the observed reality, flip `verified: true`, and only
then write ingestion. Three questions in particular are load-bearing and the probe is built
to answer them:

1. **Does `mspd_table_3_market` expose `maturity_date` per CUSIP across the full history?**
   If not, WAM — the single most important original calculation here — needs a different
   source. See Open Question 1.
2. **Does `auctions_query` publish low/median yield and allotment-at-high?** If yes, it
   materially upgrades the auction stress score. See Deviation D3.
3. **Is TIPS `outstanding_amt` par or inflation-adjusted?** This decides whether MSPD deltas
   can be used for net issuance at all. See Deviation D2.

Everything below is source-independent design and stands regardless of the probe outcome.

---

## 3. Architecture and layering

Directory layout as specified in the brief. The layering rule is enforced, not aspirational:

```
ingestion/      → writes data/raw/**.parquet, exactly as retrieved. No cleaning, no maths.
transformation/ → raw → data/processed/**.parquet, normalized long tables. Typed here.
calculations/   → reads processed only. Pure functions, no I/O, no config reads at call time.
signals/        → composes calculations into scores. Weights injected, never imported.
validation/     → cross-checks against official published figures. Fails loudly.
app/            → reads data/processed only. Never calls an API at page load.
```

Concretely: `calculations/` functions take DataFrames and explicit parameters and return
DataFrames. They do not open files or read YAML. That is what makes them testable against
hand-computed fixtures, which is the whole point of the test requirement.

**Typed parsing layer.** `ingestion/fiscaldata.py` gets one `parse_typed(rows, schema)` entry
point: everything arrives as strings with nulls as the literal `"null"`, so coercion is
centralised and declared per field (date / decimal / integer / category), never inferred by
`pd.read_json`. A value that fails coercion becomes NaN **and** increments a parse-failure
counter surfaced on the Data Quality page — silent coercion failure is the classic way bad
numbers reach a dashboard.

**Provenance on every row.** `source`, `retrieval_date`, `observation_date`, plus
`publication_date` and `revision_flag` where applicable (see D4).

---

## 4. Proposed schema

Long-format parquet. `country` is a first-class dimension everywhere despite Phase 1 being
US-only. Amounts are stored in **units of one currency unit** (not millions) with an explicit
`currency` column, so Phase 3 multi-sovereign aggregation never inherits a units bug.

### `debt_outstanding`
| column | type | note |
|---|---|---|
| `observation_date` | date | MSPD month end |
| `publication_date` | date | when Treasury released it (D4) |
| `country` | category | `US` |
| `security_class` | category | `BILLS, NOTES, BONDS, TIPS, FRN, OTHER, TOTAL_MARKETABLE` |
| `amount_outstanding` | float64 | par unless flagged |
| `amount_basis` | category | `PAR` / `INFLATION_ADJUSTED` (D2) |
| `currency` | category | `USD` |
| `source`, `retrieval_date` | str, timestamp | |

`TOTAL_MARKETABLE` is stored as its own published row, never as a sum of the parts — that is
what makes the reconciliation check in §6 meaningful.

### `securities_detail` (WAM input)
`observation_date, country, cusip, security_class, issue_date, maturity_date,
amount_outstanding, amount_basis, interest_rate, currency, source, retrieval_date`

### `auctions`
`auction_date, issue_date, country, security_class, term, cusip, amount_offered,
amount_accepted, bid_to_cover, high_yield, low_yield, median_yield, allotment_at_high_pct,
primary_dealer_pct, direct_pct, indirect_pct, tail_proxy_bps, tail_proxy_method,
source, retrieval_date`

`tail_proxy_method` is a stored column, not a footnote — a row must state which proxy
produced its tail, because the available method changes across history (D3).

### `net_issuance` (derived)
`period_start, period_end, frequency {M,Q}, country, security_class, net_issuance,
method {mspd_delta, mspd_delta_accretion_adjusted}, quality_flag, retrieval_date`

### `term_premium`
`date, country, maturity {2Y,5Y,10Y}, model {ACM,KW}, value, vintage_date, revision_flag,
source, retrieval_date`

`vintage_date` + `revision_flag` are what make ACM re-estimation detectable rather than
silently destructive.

### `qra_log` (manual)
As specified in the brief, with `entered_by` and `source_url` mandatory and validated
non-empty at entry.

### `rates`, `fiscal`, `liquidity`
`date, country, series_id, value, frequency, source, retrieval_date`

### `data_quality_events`
`event_date, source, endpoint, event_type {fetch_failure, contract_break, staleness,
parse_failure, revision, reconciliation_break}, severity, detail, retrieval_date`

A first-class table rather than log scraping, so the Data Quality page is a query and CI can
assert on it.

---

## 5. Recommended deviations from the brief

Ranked by how much they affect whether the output is defensible.

### D1 — Percentile normalization must be point-in-time, or the backtest proves nothing (HIGH)
The brief specifies percentile-rank normalization (agreed — more explainable than z-scores)
and a 2001–present backtest. If percentiles are computed over the full sample, a 2005 reading
is ranked against data through 2026 and the backtest is look-ahead contaminated. It would
show the 2020 spike beautifully and mean nothing.

**Recommendation:** all percentile ranks used in the score are computed on a trailing or
expanding window *as of each date*, with a minimum-history requirement before the score
publishes at all (proposed: 5 years, config). The dashboard's live reading and the backtest
then use identical code. I'd additionally store a full-sample variant clearly labelled
"in-sample, descriptive only" for chart context. This is the single most important change.

### D2 — TIPS outstanding includes inflation accretion, so ΔMSPD is not net issuance (HIGH)
Month-over-month change in TIPS outstanding conflates net issuance with CPI accretion. In a
high-inflation stretch (2021–2023 — exactly the period of interest) accretion is large and
would show as phantom TIPS "issuance", inflating the coupon denominator and *understating*
the incremental bill funding ratio. The bias runs against the thesis, which makes it
especially important to remove.

**Recommendation:** confirm the reporting basis via the probe. If inflation-adjusted, either
(a) adjust using index ratios, or (b) exclude TIPS from the net-coupon aggregate and report
it as its own series, documenting the choice. Bills, notes, bonds and FRNs are clean under
MSPD deltas; only TIPS is contaminated. Cross-check total gross issuance and redemptions
against the Daily Treasury Statement as an independent validation of the delta method.

### D3 — Use published bid dispersion instead of an invented tail (HIGH)
The brief correctly refuses to fabricate a tail without 1pm when-issued yields. But the
proposed substitute — high yield vs prior-close CMT — is weak in a specific way: DGS is a
close-of-day *constant-maturity par* yield, not the auctioned security's yield, so the "tail"
absorbs a full day of market movement plus a maturity-point mismatch. It is dominated by
noise unrelated to auction quality.

**Recommendation:** if the probe confirms `low_yield` / `median_yield` / allotment-at-high
are published, use **high-minus-median yield spread** and **allotment-at-high %** as the
dispersion measures. These are genuine, official, free measures of exactly what a tail
proxies for — how far bidders had to be reached to clear the auction — with no when-issued
data required. Keep the CMT-based proxy as a labelled diagnostic at default weight 0, and
publish a weight-sensitivity table. If those fields turn out not to exist, fall back to the
brief's method and document the noise properties honestly.

### D4 — Carry `publication_date`, not just `observation_date` (HIGH)
MSPD for month end *M* publishes around the 8th business day of *M+1*. A dashboard that
displays a bill share dated month-end without stating it was unknowable for another five
weeks invites a timing error, and any Phase 4 forward-return work built on observation dates
is straightforwardly wrong.

**Recommendation:** add `publication_date` to the schema now (done above), display "data as
of / published" on every KPI card, and make Phase 4 forward returns align on publication
date. Cheap now, expensive to retrofit.

### D5 — Debt-ceiling episodes distort every issuance ratio (HIGH for interpretation)
During a binding ceiling Treasury runs down bills and total net borrowing approaches zero:
the Incremental Bill Funding denominator collapses and the ratio becomes meaningless or
wildly negative. Worse, the post-resolution bill surge (2023 being the cleanest case) is a
mechanical rebuild of the TGA, not a strategic duration decision — and it will read as a
maximum-strength thesis confirmation.

**Recommendation:** the brief's magnitude floor on the denominator is necessary but not
sufficient. Add a config-driven `debt_ceiling_episodes` list (binding start / resolution
date) in `thresholds.yaml`; shade those windows on charts, flag affected rows in
`net_issuance.quality_flag`, and report backtest results both with and without them. This is
the most likely source of a false positive in the whole system and should be handled
explicitly rather than by a magnitude guard.

### D6 — Two of the six score factors are near-mechanically collinear (HIGH)
Factor 2 (Incremental Bill Funding %) and factor 6 (coupon issuance restrained vs financing
need) are close to arithmetic complements: if borrowing rises and coupons are held flat,
bills absorb the residual by construction. Factor 1 (Bill Share level trend) is the stock
counterpart of factor 2's flow. Under equal weights, the composite is therefore roughly
50–65% "bills" and only ~35% market-price evidence (term premium, auction stress) — so the
score will tend to confirm the thesis using one fact counted three ways.

**Recommendation:** group the factors explicitly and weight the groups, not the factors:

- **Quantity / issuance behaviour** (bill share trend, incremental bill funding, WAM trend,
  coupon restraint)
- **Market price / absorption evidence** (10Y term premium trend, long-end auction stress)

Proposed default 50/50 group weights, with within-group weights configurable — keeping full
flexibility in `factor_weights.yaml` while stopping equal weighting from silently
double-counting. Publish the factor correlation matrix in the backtest so the collinearity is
visible and the weighting choice is falsifiable. The interaction flag (bill share rising AND
term premium rising) matters precisely *because* it requires both groups to agree, so it
should be surfaced as the brief specifies.

### D7 — Do not commit full CUSIP-level history to git (MEDIUM-HIGH, practical)
`securities_detail` is a few thousand CUSIPs per month over ~25 years — millions of rows, and
Actions would rewrite it on every run. Streamlit Community Cloud deploys from the repo, so
the repo carries whatever the app needs, and git history bloat here is permanent.

**Recommendation:** commit the derived WAM/maturity-bucket time series (small) plus the
latest CUSIP snapshot only; keep full historical detail in `data/raw/` partitioned by year,
incrementally refreshed for recent months only, and git-ignored. Backfills are reproducible
by re-running ingestion. If full history in-repo is wanted later, git-lfs — decide before
the first big commit, not after.

### D8 — Define the frequency-alignment convention for the interaction flag (MEDIUM)
Bill share is monthly; ACM term premium is daily. "Both rising" needs one stated convention.
**Recommendation:** resample term premium to month-end, compare rolling 3m/6m/12m changes on
a common monthly axis, and state it in `methodology.md`. Never forward-fill monthly data onto
a daily axis for signal purposes (same rule for FRED's quarterly `MMMFFAQ027S`).

### D9 — WAM conventions must be pinned before the number is quoted (MEDIUM)
Four conventions change the answer: (a) final maturity for FRNs and TIPS; (b) par vs
inflation-adjusted weighting for TIPS (ties to D2); (c) callable bonds in the 2001–2009
history, where call date vs maturity date differ; (d) whether non-marketable debt is excluded
(it is — marketable only).

**Recommendation:** pin all four in `config/thresholds.yaml`, document in
`data_dictionary.md`, and validate against Treasury's own published average length of the
marketable debt (QRA/Treasury Bulletin) as the external check. A WAM that cannot reproduce
Treasury's published figure within tolerance is not fit to be published.

### D10 — Add the TBAC bill-share reference band (LOW-MEDIUM)
TBAC has long referenced a bill share around 15–20% of marketable debt as the recommended
range. A config-driven reference band on the bill share chart converts a line into a
judgement: it shows not just that bill share rose, but that it is outside the range
Treasury's own advisory committee recommends. Value stated in config, sourced, not hardcoded.

### D11 — Disclose ACM revision bias in the backtest (documentation)
The backtest uses today's ACM vintage for history, because point-in-time ACM vintages are not
freely available. Term premium history is therefore revised data used as if it were
real-time. This cannot be fixed, only disclosed, and `THREEFYTP10` (Kim-Wright) provides an
independent model cross-check. Goes in `methodology.md` under known limitations.

---

## 6. Validation plan

Validation failures are errors, not warnings. The Actions workflow fails the run.

1. **Reconciliation:** Σ `securities_detail.amount_outstanding` by class vs published MSPD
   Table 1 totals, per month. Tolerance configurable, proposed 0.1%. Break → error.
2. **Independent total check:** MSPD total marketable vs Debt to the Penny, latest month.
3. **WAM external check:** computed WAM vs Treasury's published average length of marketable
   debt, where a published figure is available.
4. **Contract check:** `probe_sources.py` contract logic runs against each refresh; a field
   that disappears or changes type fails the run rather than producing NaN columns.
5. **Continuity:** expected observation count per feed per period; gaps recorded in
   `data_quality_events`, never interpolated.
6. **Staleness:** per-source max age thresholds in config; breach surfaces on the Data
   Quality page and fails the workflow.
7. **Revision detection:** each ACM pull diffed against the prior vintage; changed historical
   values raise `revision_flag` and a data-quality event.

---

## 7. Test plan

`pytest`, hand-computed fixtures, no golden files generated by the code under test.

- **WAM:** synthetic 3-security fixture with WAM computed by hand in the test docstring;
  plus edge cases — security maturing on the valuation date, zero outstanding, a maturity
  before the valuation date (must raise, not silently go negative).
- **Bill share:** including the case where subtotal/total rows are present in the input and
  must be excluded.
- **Net issuance deltas:** including a month with a missing prior observation (must produce
  NaN, not a fabricated delta against the last available month).
- **Incremental funding %:** denominator at, just above and just below the floor; negative
  denominator; exactly zero.
- **Auction stress:** known z-inputs → known composite; fewer than 12 trailing auctions
  (must return NaN, not a partial-window score).
- **Percentile ranks:** point-in-time correctness — assert that a percentile at date *t* is
  unchanged by appending later data. This is the regression test for D1.
- **Typed parsing:** `"null"` → NaN, thousands separators, negatives in parentheses if
  present, and parse-failure counting.

---

## 8. Build sequence

Each step ends green and committed.

| # | Step | Gate |
|---|---|---|
| 0 | Probe sources, correct `sources.yaml`, flip `verified` | **blocked on network access** |
| 1 | Typed parsing layer + fiscaldata client (pagination, retry, raw parquet) | tests |
| 2 | MSPD Table 1 ingestion → `debt_outstanding` | reconciliation vs Debt to the Penny |
| 3 | Bill share + net issuance + incremental funding | tests, D2/D5 guards in place |
| 4 | `securities_detail` ingestion → WAM + maturity buckets | reconciliation vs Table 1 |
| 5 | FRED + NY Fed ACM ingestion, revision detection | vintage diff test |
| 6 | Auctions ingestion + rolling stats + stress score | tests, D3 method recorded |
| 7 | Validation + `data_quality_events` | breaks fail loudly |
| 8 | Streamlit: Home, then subpages | reads processed only |
| 9 | QRA input page + Data Quality + Methodology | manual-entry validation |
| 10 | Actions refresh workflow | fails loudly on any feed error |

**Phase 1 definition of done:** every published number traces to an official source; the
reconciliation checks pass; the app renders from `data/processed` with no network calls; the
test suite is green; `methodology.md` and `data_dictionary.md` are current. Phase 2 does not
begin until then, per the brief.

---

## 9. Open questions for the user

1. **WAM source (blocking for step 4).** If `mspd_table_3_market` lacks per-CUSIP maturity
   dates over full history, options are: (a) shorter WAM history from wherever detail does
   exist; (b) TreasuryDirect `TA_WS` securities endpoint as the detail source; (c) publish
   only Treasury's own average-length series and drop the independent calculation. My
   preference is (b) then (a) — an independently computed WAM that reconciles is worth real
   effort, since it is what lets you see maturity-bucket composition rather than one number.
2. **Group weighting (D6).** Do you accept 50/50 quantity vs market-price group weights as
   the default, or prefer flat equal weights across the six factors with the collinearity
   documented?
3. **History depth for auctions.** Bidder-class detail is materially richer from 2008. Start
   the auction stress series in 2008 and leave earlier auctions out of the composite, or
   include earlier auctions with a reduced factor set and a quality flag?
4. **Repo data policy (D7).** Confirm full CUSIP history stays out of git.

---

## 10. Deviations I am *not* recommending

For the record, these parts of the brief I think are right as written and would push back on
changing: percentile ranks over z-scores for the headline score; refusing to NLP-extract QRA
PDFs in Phase 1; country as a dimension from day one; MSPD deltas as the net-issuance method
(with D2's TIPS fix) rather than reconstructing from auction data, which would miss buybacks
and non-competitive detail; and the rule that missing data stays visibly missing.
