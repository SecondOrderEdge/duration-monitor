# Reconciling WAM against Treasury's own figure

`build_wam` computes **5.816 years (69.8 months)** at 2026-07-31 from per-security
MSPD detail. Nothing checks it against Treasury's published number, so a
systematic error in the maturity weighting would look exactly like a correct
answer. This records how far that check got and what blocks it.

## Treasury does not publish it as data

Probed 2026-08-19 across `mspd_table_2` through `mspd_table_5` and
`avg_interest_rates`: **no Fiscal Data endpoint reports an average maturity or
average length.** The figure is not in the structured estate.

## And in the quarterly deck it is a chart, not a sentence

The Office of Debt Management's quarterly refunding presentation carries it under
"III. Portfolio Metrics — A. Weighted Average Maturity of Marketable Debt
Outstanding". Extracting that slide's text yields:

> `40 45 50 55 60 65 70 75 80 85 1980 1982 ... 2024 Weighted Average Maturity
> (Months) Calendar Year`

That is the **y-axis tick labels and the x-axis years**. The current value is
plotted geometry, not text. Fifteen documents mention the term with no
extractable value beside it.

So the axis tells us ODM's series is quoted in **months** and spans roughly
**40–85**. Our 69.8 falls inside that range — which is not a reconciliation, it
is a sanity check that would pass for any plausible wrong answer too.

**PDF text extraction cannot reconcile WAM against the current deck.** That is a
property of the source, not a defect in the probe.

## What is still viable

**Historical decks state values in prose.** The 2009-era presentations say things
like "maturity of issuance settle to approximately 68 and 79 months" and "Average
maturity of total debt outstanding rose by...". Our WAM series runs from 2001, so
dated statements from 2009-2016 decks can be compared against our value for the
same month. That tests the pipeline over the history the backtest actually uses,
which is worth more than matching a single current number.

The blocker is dating: ODM decks are published under labels like "2nd Quarter"
with no year in the URL or link text — the same problem that left the TBAC
citations undated.

## Three metrics that must not be conflated

| metric | population | units |
|---|---|---|
| ours | all marketable, par basis, final maturity for FRN/TIPS | years |
| ODM "Weighted Average Maturity of Marketable Debt Outstanding" | all marketable | **months** |
| Treasury Bulletin "average length" | marketable held by **private investors** | months |
| ODM **WANRR** | all marketable, to next RATE RESET not maturity | months |

The third excludes Federal Reserve holdings, so it moves with SOMA rather than
with issuance; a close match against it would be coincidence.

The fourth was found in the current deck, described in Treasury's own words as
"a 'Weighted Average Maturity' metric" — Weighted Average Next Rate Reset. For a
floating-rate security the next reset is not the maturity, so WANRR is a
different number wearing a very similar name. Anything reconciling against
"Treasury's WAM" has to establish which of these four it has.

## Probe noise, still present

The value matcher pairs "average maturity" with any number within 160 characters,
so projection language — "over the next 10 years", "shocked higher after 10
years" — produces spurious hits like `10.0 year` and `75.0 year`. Twenty values
were returned and most are this. Requires adjacency, not proximity, before any
extracted number is trusted.

## Coverage of the run

41 documents examined, 39 with text, **782 left unread** on the time budget after
the archive hop widened discovery to 823 candidates.
