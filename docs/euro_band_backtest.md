# Should the quantity-only variant get interpretation bands back?

`validated_for_variants: [full]` currently withholds the score bands from
DE/FR/IT, so those countries publish a number with no label. That was justified
on distribution width: the quantity-only score runs sd 23.4 against the US 19.2,
so fixed cut-points at 0/20/40/60/80/100 reach further into the tail than the
backtest ever tested.

This is the proper test of that decision — whether the bands would *mean*
anything for this variant, judged the way the US bands were: against named
episodes.

## The score responds correctly at episodes

Mean quantity-only score by country:

| episode | DE | FR | IT |
|---|---|---|---|
| GFC, 2008-Q3 to 2009-Q2 | **88.7** | **82.5** | 53.4 |
| Sovereign crisis, 2011-Q3 to 2012-Q3 | 46.2 | 30.5 | 50.6 |
| COVID, 2020 | **87.8** | **77.2** | **74.4** |
| Energy shock, 2022-Q2 to 2023-Q1 | 29.3 | 39.3 | 49.7 |

Both crises where sovereigns visibly flooded the bill market — 2008 and 2020 —
read as aggressive shortening. 2022, a year of long-dated issuance ahead of the
rate cycle, reads as extension. That is the right ordering and it is real signal:
**the measurement works.**

## But the extremes are not episodic, and that is what bands require

A band only earns its name if reaching it is informative. Counting readings in
the two most severe bands (score below 20 or at/above 80):

| | extremes | share of readings | distinct years they occur in |
|---|---|---|---|
| US, monthly, six factors | 24 | 10% | **7 of 20** — 2008-2012 and 2023-2024 |
| euro, quarterly, three factors | 43 | 24% | **16 of 20** |

The US extremes cluster: they fire during the financial crisis and its aftermath,
then again recently, and are silent for a decade in between. The euro extremes
fire in 2013, 2014, 2015, 2018, 2019, 2022, 2023, 2024 and 2025 — ordinary years
with nothing to identify. Roughly half fall outside any crisis window on any
reasonable definition.

## Persistence fixes the frequency, not the meaning

Requiring a reading to hold for consecutive quarters before it counts:

| requirement | extremes | share | in crisis years |
|---|---|---|---|
| 1 quarter | 43 | 24% | 51% |
| 2 quarters | 22 | **12%** | 55% |
| 3 quarters | 14 | 8% | 50% |

Two quarters brings the frequency to 12%, essentially the US's 10%. **The
episodic concentration does not move** — 51%, 55%, 50%. Tuning the threshold
until the count matches would have produced a band that looks calibrated and
identifies nothing.

## Decision: bands stay withdrawn

The original justification was distribution width. The stronger one is this: the
extremes do not mark events, and no persistence rule makes them. A quantity-only
score is a good relative measure of a sovereign against its own recent behaviour
and a poor absolute classifier, which is exactly what the band names claim to be.

Note this is not a defect in the score. Its episode means are right and its
direction is right. Three correlated quantity factors at quarterly frequency
simply carry less information per reading than six including two market prices at
monthly frequency, and fixed cut-points on a 0-100 scale demand more information
than this variant has.

## What would justify restoring them

Any ONE of:

1. **More factors.** If DMO auction data or maturity profiles are found for
   DE/FR/IT (option 2 of `phase3_source_assessment.md`), the variant gains market
   evidence and an absolute anchor, and this test should be re-run.
2. **Extremes that cluster.** Re-run this comparison after any change to the
   factors or weighting. If the euro extremes fall to something like 7-9 distinct
   years, concentrated on episodes, the bands mean something.
3. **Bands derived from euro episodes rather than inherited.** Cut-points set
   from where the score actually sits during 2008, 2011-12, 2020 and 2022 — with
   the caveat that four episodes across three countries is thin evidence for five
   thresholds, and that fitting them risks describing the sample rather than the
   world.

Until then the app shows the score, each factor's rank and weight, and the
absolute 4q bill-share change. That is more information than a band, and none of
it claims more than it can support.
