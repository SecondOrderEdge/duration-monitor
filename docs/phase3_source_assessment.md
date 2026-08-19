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
| **ECB** (`data-api.ecb.europa.eu`) | SDMX-JSON | DE, FR, IT and 30 others |
| **Eurostat** (`ec.europa.eu/eurostat`) | JSON-stat | all EU member states |
| **BIS** (`stats.bis.org`) | SDMX-XML | cross-country |
| **OECD** (`sdmx.oecd.org`) | SDMX-XML | cross-country |
| UK DMO | HTML only at the URLs probed | UK |
| Japan MOF | HTML only at the URLs probed | JP |
| Finanzagentur / AFT / Italian MEF | HTML only at the URLs probed | DE / FR / IT |

The four statistical agencies serve structured data. The five national debt
offices served landing pages at the URLs probed — which does not mean they have
no data endpoint, only that none was found without guessing at one.

## The strong result: ECB securities issues statistics

The `SEC` dataflow carries the dimensions this project needs:

- `SEC_ISSUING_SECTOR` — **S131 Central government**, separable from state, local
  and social security funds.
- `SEC_ITEM` — **F33100 short-term** and **F33200 long-term** securities, with
  long-term further split into **F33201 fixed rate** and **F33202 floating rate**.
- `DATA_TYPE_SEC` — both **1 outstanding amounts (stocks)** and **4 net issues
  (flows)**, plus gross issues and redemptions separately.
- `FREQ` — **monthly**.
- `REF_AREA` — 33 reference areas including the three euro-area sovereigns.

Stocks *and* flows, monthly, by maturity class, for central government. That is
the bill share and the incremental bill funding ratio — two of the six factors —
from a single publisher on one basis, without deriving flows from stock deltas
the way the US series has to. Net issues being published directly is better than
what MSPD offers, where net issuance is inferred from month-over-month change and
carries the TIPS accretion problem with it.

Eurostat `gov_10q_ggdebt` covers the same ground quarterly (`F31` short-term,
`F32` long-term, sector `S1311` central government) and adds `PC_TOT`, the share
of total, computed by the publisher. It is a useful cross-check on the ECB
figures rather than a replacement, being quarterly.

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
| Bill share trend | yes | **yes** (ECB stocks) | not yet found |
| Incremental bill funding | yes | **yes** (ECB net issues) | not yet found |
| Coupon restraint | yes | **yes** (ECB flows) | not yet found |
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

Option 1 with 2 pursued in parallel is the honest path. What must not happen is
scoring Japan on three factors and the US on six and putting both under one
heading — the brief's own instruction is that country is a first-class dimension,
and that has to include which inputs each country's number is built from.

## Open questions before any Phase 3 ingestion

1. **Does the ECB series carry enough history?** The probe requested one
   observation to read the dimensions. Coverage start per country is unknown and
   matters: the point-in-time percentiles need 60 months of history before the
   score publishes at all.
2. **What is the euro-area equivalent of the debt-ceiling problem?** The US cash
   adjustment exists because a ceiling resolution mechanically inflates bill
   issuance. The euro area has no debt ceiling but does have its own distortions.
3. **Is `S131` central government the right sector**, or does the comparison need
   general government to be consistent with how each DMO reports?
4. **Do the UK and Japan have structured endpoints at all?** Until that is
   answered, they are not Phase 3 candidates so much as Phase 3 aspirations.
