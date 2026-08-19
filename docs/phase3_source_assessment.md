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
- Coverage, from the first live pull (2026-08-19): **2000-Q1 to 2026-Q1, 105
  quarters**, identical for Germany, France and Italy, fully dense — 630 values
  for 3 countries x 2 instruments x 105 quarters, with nothing missing.

### Correction: 105 quarters, not 129

The discovery probe reported 1994-Q1 to 2026-Q1 and this document called it
thirty-two years of history "deeper than the US series". The first live pull of
the actual slice the score uses returns **2000-Q1**. The probe was counting the
`time` categories the *dataflow* carries, across every sector and instrument;
central government (S1311) short- and long-term debt securities in MIO_EUR — the
combination the factors are built from — starts six years later.

Same mistake as the ECB one, in a smaller size: the dimension catalogue describes
what the dataset can express, not what any particular cell of it contains. Read
per slice, not per dataflow.

So the euro-area history is one year deeper than the US series (2001), not
thirty-two. 105 quarters is still comfortably past the 20-quarter minimum, and
after the four-quarter horizon and the 20-quarter percentile warm-up the first
scored quarter is 2006-Q1. Nothing about the design changes; the claim was just
wrong.

### The response carries a `freq` dimension

Live dimensions are `['freq', 'na_item', 'sector', 'unit', 'geo', 'time']` — six,
not the five this document implied, and in an order no fixture guessed. It
decoded correctly because `decode_jsonstat` derives its stride arithmetic from the
response's own `id` and `size` lists rather than assuming a layout. Had it
assumed one, every value would have been attributed to the wrong country and the
table would have looked entirely well-formed.

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

1. **RESOLVED — history is not the constraint.** Eurostat runs 2000-Q1 to
   2026-Q1 for all three countries, 105 quarters (corrected from 129 above). The
   constraint is frequency (quarterly) and breadth (three factors), not depth.
2. **What is the euro-area equivalent of the debt-ceiling problem?** The US cash
   adjustment exists because a ceiling resolution mechanically inflates bill
   issuance. The euro area has no debt ceiling but does have its own distortions.
3. **Is `S1311` central government the right sector**, or does the comparison
   need general government to be consistent with how each DMO reports? Central
   government is what is implemented, because the US series is Treasury debt
   rather than general government — but the euro-area DMOs report against their
   own perimeters and this has not been checked against any of them.
4. **The ratio floor is now calibrated, and it is per country.** Live medians for
   |net borrowing| per quarter are DE 9,647mn, FR 21,533mn, IT 25,664mn. Germany
   borrows less than half what the other two do, so a single shared floor would
   mask about half of German quarters against a quarter of French and Italian
   ones — three countries on one axis, scored on different amounts of their own
   history. Each floor is 38% of that country's own median, the fraction the US
   floor already implies. Recorded in `config/thresholds.yaml`.
5. **Do the UK and Japan have structured endpoints at all?** Until that is
   answered, they are not Phase 3 candidates so much as Phase 3 aspirations.

## The band labels do not mean what they say for this variant

Found on the first live scoring run, and it is the most important thing on this
page.

Every factor in `quantity_only` is a **point-in-time percentile rank**, so it
measures a quarter against the country's own recent behaviour, never against
zero. The band names — "meaningful shortening", "aggressive shortening" — assert
an absolute direction the score cannot support.

France, 2026-Q1, from the live run:

| factor | raw | rank | trailing 40q median | share negative |
|---|---|---|---|---|
| bill_share_trend | −0.0021 | 67.5 | −0.0057 | 70% |
| incremental_bill_funding | +0.1234 | 57.5 | +0.1116 | 39% |
| coupon_restraint | −0.9628 | 67.5 | −1.0438 | 100% |

Score 63.4, band "meaningful shortening". **France's bill share fell 0.21pp over
those four quarters.** It has fallen in 70% of the last 40 quarters, median 4q
change −0.57pp. At −0.21pp France is extending more slowly than usual, ranks at
the 68th percentile of its own decade, and the composite reports shortening.

This is not a sign error. The distributions above confirm the convention is
right: raw sits above the trailing median in each case, so a rank above 50 is
arithmetically correct. Italy behaves identically (raw −0.0009 against a median
of −0.0016, 68% negative, rank 60.0). The measurement is doing exactly what it
was built to do — the *label* is making a claim the measurement never made.

Why it bites here and not on the US score: six factors, two of them market
prices, give the US composite an absolute anchor, and the regime classifier
demands corroboration before escalating. A three-factor quantity-only score has
no anchor at all. All three factors are relative, so the entire composite is
relative, and a sovereign in a persistent extension trend will score above 50
whenever it extends less than usual.

Mitigation, pending a decision on the band names themselves: the raw unranked
`bill_share`, `bill_share_4q_change` and a `direction_absolute` of
extending/shortening/flat now ship on every scored row, along with
`score_is_relative_to_own_history`. The app must show the absolute direction next
to the score. A relative reading presented as an absolute one is precisely the
failure the variant mechanism exists to prevent, and the variant label alone does
not prevent it.

### RESOLVED: not renamed — withdrawn

The question was whether to give the bands variant-specific names. Measuring
first turned up a bigger problem than the wording.

Band cut-points are fixed at 0/20/40/60/80/100, so what they mean depends
entirely on how wide the score's distribution is. Measured 2026-08-19 on live
data, 234 US months against 179 euro-area quarters:

| | sd | in the two most severe bands |
|---|---|---|
| US, `full` | 19.2 | 10.3% |
| euro area, `quantity_only` | 23.4 | **24.0%** |
| — Germany alone | 25.4 | **29.5%** |

The same cut-points fire "strong duration extension" or "aggressive shortening"
2.3 times as often on the quantity-only variant. Not because those sovereigns
are twice as erratic, but because three correlated quantity factors with no
market-price anchor diversify less than six with two orthogonal ones, so the
composite is wider and the fixed cuts reach much further into the tail than the
backtest ever tested.

So the bands are **miscalibrated for this variant, not merely misnamed**, and
renaming would have given more careful-sounding words to thresholds that still
had no evidence behind them. `validated_for_variants: [full]` now gates them and
`bands_for_variant` returns None for anything else: a quantity-only score ships
with no band at all. Same standard that already denies these scores a regime.

Recalibrating the cuts per variant was considered and rejected. Matching the band
FREQUENCIES across variants assumes each should have the same share of severe
readings, which is assuming the answer; and calibrating cuts on the full sample
is the look-ahead contamination D1 exists to prevent.

What a reader gets instead of a band: the score, each factor's point-in-time rank
and weight, the absolute 4q bill-share change, and the bill-share level. That is
strictly more than the band conveyed, and none of it asserts something unproven.

To bring bands back, backtest them against named euro-area episodes — the
2011-12 sovereign crisis, 2020, the 2022 energy shock — the way the US bands were
validated against 2008, 2011, 2020 and 2021.
