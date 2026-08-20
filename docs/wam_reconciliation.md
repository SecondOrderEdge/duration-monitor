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

## CONCLUSION: the ODM decks cannot support this reconciliation

Final run, 38 documents with extractable text, **zero comparable values**. Every
one of the 21 candidate figures was rejected, and reading the rejections back
shows all of them were rejected correctly:

| rejected | reason |
|---|---|
| 8 | a horizon, not a level — "over the next 10 years", "next 75 years" |
| 6 | a projection — "settle to approximately 68 and 79 months" |
| 5 | chart axis labels |
| 2 | average maturity of ISSUANCE, not of the stock |

The decisive extract is the chart itself:

> `20 30 40 50 60 70 80 90 months  Average Maturity of Issuance 1/  Average
> Maturity of Marketable Debt Outstanding 2/`

Both series are plotted on one chart with a months axis. **ODM states average
maturity of the outstanding stock only as projections and as chart geometry.
There is no current actual value in extractable prose**, in the current decks or
the historical ones.

The 51-month figure that looked most promising reads in full: "over the next 5
years: Average maturity of total outstanding and average maturity of issuance
settle to about 52 and 51 months, respectively" — a five-year projection, and 51
is the issuance leg. Comparing it to our series would have produced a confident
false discrepancy from a number that is neither current nor our metric.

This is a finding about the source, not a probe defect. Text extraction is the
wrong instrument, and no further iteration on it is warranted.

## What would actually close this

1. **Transcribe one checkpoint by hand.** Read the current value off ODM's chart,
   record it in config with the deck and date, and mark it `transcribed` — not
   `verified`, because nothing fetched it. One dated point is enough to catch a
   systematic weighting error, which is the risk that matters.
2. **Open the Quarterly Release Data file.** It extracted 126,910 characters and
   has never been examined; if it is tabular it may carry the series directly.
3. **Accept the internal check and say so.** WAM already reconciles against
   published MSPD subtotals across 935 (month, class) pairs, worst case 1.59%.
   That tests the arithmetic against Treasury's own totals. It does not test the
   maturity convention, which is what an external comparison would add.

## Coverage of the runs

41 documents examined, 38-39 with text, **~783 left unread** on the time budget
after the archive hop widened discovery to 823 candidates. The unread remainder
is overwhelmingly chart decks, which the above shows cannot answer the question
anyway.
