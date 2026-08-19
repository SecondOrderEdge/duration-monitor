# Phase 3 source assessment

What is actually available for Japan, the UK, Germany, France and Italy, and
therefore what the global score can and cannot be. Evidence in
`docs/source_probe/phase3/`.

Nothing here is verified in the sense `config/sources.yaml` uses the word — no
field list has been declared yet. This is discovery: the dimensions below were
read from live responses, but no contract has been written against them.

## Where the probe had to run

Every candidate publisher is refused by the development environment's network
policy (403 at CONNECT) while the Phase 1 hosts are permitted, so the probe runs
in GitHub Actions. That is the same arrangement FRED uses. All nine publishers
are reachable from there.

## What each publisher serves

| publisher | machine-readable | covers |
|---|---|---|
| **ECB** (`data-api.ecb.europa.eu`) | SDMX-JSON | DE, FR, IT — **but discontinued 2022-03** |
| **Eurostat** (`ec.europa.eu/eurostat`) | JSON-stat | all EU member states |
| **BIS** (`stats.bis.org`) | SDMX-XML | cross-country |
| **OECD** (`sdmx.oecd.org`) | SDMX-XML | cross-country |
| UK DMO | HTML only at the URLs probed | UK |
| Japan MOF | HTML only at the URLs probed | JP |
| Finanzagentur / AFT / Italian MEF | HTML only at the URLs probed | DE / FR / IT |

The four statistical agencies serve structured data. The five national debt
offices served landing pages at the URLs probed — which does not mean they have
no data endpoint, only that none was found without guessing at one.

## Correction: the ECB series is discontinued

An earlier version of this document called the ECB securities issues statistics
the strong result. That was wrong, and the error is instructive.

The dimensions were real and were read from live responses: `SEC_ISSUING_SECTOR`
does separate **S131 central government**, `SEC_ITEM` does split **F33100
short-term** from **F33200 long-term**, and `DATA_TYPE_SEC` does carry both
**outstanding stocks** and **net issues as published flows**, monthly, for 33
reference areas. Deriving the real series keys from the API confirmed the series
exist: 36 of the dataflow's 40,633 series match central government, monthly,
short or long-term, stocks or flows, for Germany, France and Italy.

Every one of those 36 runs **2012-12 to 2022-03**.

A uniform end date across every country, every maturity and both data types is a
discontinued dataflow, not a data gap. The dimension catalogue describes what the
dataflow *can* express; it says nothing about whether anyone is still publishing
into it. A monitor of current conditions cannot use a series that stopped four
years ago, however good its structure.

The lesson is the same one the Phase 1 probe kept teaching: a source has to be
checked for what it actually contains, not just what it is shaped to contain.
Reachable, well-structured and current are three separate questions.

## The actual euro-area source: Eurostat

`gov_10q_ggdebt` carries the same split and is current:

- `na_item` — **F31 short-term debt securities**, **F32 long-term debt
  securities**, alongside F3 (all debt securities), F4 loans, F2 currency and
  deposits.
- `sector` — **S1311 central government**, separable from state, local and
  social security funds.
- `unit` — MIO_EUR, MIO_NAC, PC_GDP and **PC_TOT**, the share of total computed
  by the publisher.
- Coverage, verified per country: **1994-Q1 to 2026-Q1, 129 quarters**, identical
  for Germany, France and Italy.

Thirty-two years of history, current to the most recent quarter, harmonised
across member states. That is deeper history than the US series, which starts in
2001.

Two costs relative to what the ECB dataflow would have given:

**Quarterly, not monthly.** The US factors are monthly. A quarterly euro-area
score is a coarser instrument, and the point-in-time percentile window would need
restating in quarters. 129 quarters comfortably exceeds the equivalent of the
60-month minimum history, so this constrains resolution rather than feasibility.

**Net issuance must be derived from stock deltas**, exactly as the US series does
from MSPD, rather than read from a published flow. The earlier claim that the
euro-area data was *cleaner* than the US arrangement is withdrawn — it is the
same arrangement, with the same caveat that deltas net issuance against
redemptions within the period.

## What is not available, and what that costs

**WAM cannot be computed** for these sovereigns the way it is for the US. Both
ECB and Eurostat stop at a short-term / long-term split. There is no per-security
maturity date, so there is no weighted average maturity and no maturity buckets.
The US has an unusually good free data estate here — `mspd_table_3_market` gives
maturity dates per security for the full history, and nothing comparable turned
up for the other five.

**Auction stress cannot be computed** from any of the four statistical agencies.
It needs auction-level bid-to-cover and bidder-class detail, which lives with the
national debt offices — the ones that served HTML.

**Term premium has no equivalent source.** ACM is a New York Fed model of the US
curve. There is no reason to expect a free, comparable, published term-premium
estimate for JGBs, gilts or Bunds, and using a different model per country would
make the factor incomparable across the countries it is supposed to compare.

## The consequence for the global score

Per-country factor availability, on what has been found so far:

| factor | US | DE / FR / IT | UK / JP |
|---|---|---|---|
| Bill share trend | yes, monthly | **yes, quarterly** (Eurostat F31/F32) | not yet found |
| Incremental bill funding | yes, monthly | **yes, quarterly** (Eurostat stock deltas) | not yet found |
| Coupon restraint | yes, monthly | **yes, quarterly** (Eurostat stock deltas) | not yet found |
| WAM trend | yes | **no** | not yet found |
| 10y term premium trend | yes | **no** | **no** |
| Long-end auction stress | yes | **no** (needs DMO data) | not yet found |

So the euro-area three support **three of six factors**, all from the quantity
group. The score's `min_factors` is currently 4, which those countries would
fail — correctly, because a composite resting on three inputs is not the same
measurement as one resting on six.

That is a design decision, not a bug to code around. Three options, in order of
how defensible they are:

1. **Publish a narrower score for non-US sovereigns and say so.** A "quantity
   only" duration shift score, explicitly labelled, alongside the full US score.
   Comparable across the countries that have the same three factors; not
   comparable to the US number, and never presented as if it were.
2. **Find the missing sources.** The DMOs may publish auction results and
   maturity profiles in structured form behind URLs this probe did not guess.
   That is real work with an uncertain payoff, and it is the only route to a
   genuinely comparable six-factor score.
3. **Reduce the US score to the three factors everyone has.** Comparable by
   construction, and it throws away the market-price evidence that makes the
   thesis falsifiable. Not recommended.

**Decision: option 1**, with 2 pursued in parallel. Implemented as score
variants in `config/factor_weights.yaml`: `full` for the US and `quantity_only`
for Germany, France and Italy, with the variant carried on every scored row and
`comparable_with` declaring which variants may share an axis. A country with no
configured variant raises rather than defaulting — a score built from whatever
factors happen to exist is not a variant, it is an unlabelled measurement. What must not happen is
scoring Japan on three factors and the US on six and putting both under one
heading — the brief's own instruction is that country is a first-class dimension,
and that has to include which inputs each country's number is built from.

## Unresolved in the probe itself

The ECB dataflow listing was requested with `format=sdmx-json` and returned
something that would not parse as JSON — that resource appears to serve XML
regardless. It was being used to look for a successor to the discontinued SEC
dataflow. Not pursued further because Eurostat answers the question Phase 3
actually needed answering; worth revisiting only if monthly frequency turns out
to matter more than it currently appears to.

## Open questions before any Phase 3 ingestion

1. **RESOLVED — history is not the constraint.** Eurostat runs 1994-Q1 to
   2026-Q1 for all three countries, 129 quarters. The constraint is frequency
   (quarterly) and breadth (three factors), not depth.
2. **What is the euro-area equivalent of the debt-ceiling problem?** The US cash
   adjustment exists because a ceiling resolution mechanically inflates bill
   issuance. The euro area has no debt ceiling but does have its own distortions.
3. **Is `S131` central government the right sector**, or does the comparison need
   general government to be consistent with how each DMO reports?
4. **Do the UK and Japan have structured endpoints at all?** Until that is
   answered, they are not Phase 3 candidates so much as Phase 3 aspirations.
