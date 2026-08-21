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

## RESULT: our WAM matches Treasury's, except in 2001-2007

**The earlier conclusion on this page — that the ODM decks cannot support this
reconciliation — is WITHDRAWN.** Treasury does publish the series. The quarterly
release workbook carries a sheet `Avg. mat. of debt outstanding` holding
*"Average Maturity of Treasury Marketable Securities--Total Outstanding (in
months)"* as a Year x Jan..Dec grid, 318 months back to 2000. Four probe runs
concluded otherwise because that workbook is an `.xls` that was being decoded as
UTF-8 — which does not raise, it yields mojibake — so the file counted as
searched while carrying nothing readable.

306 months overlap, 2001-01 to 2026-06. Difference is **ours minus Treasury**, in
months:

| era | n | mean | median | worst |
|---|---|---|---|---|
| 2001-2007 | 84 | **+2.73** | **+2.87** | +5.11 |
| 2008-2012 | 60 | -0.32 | -0.34 | 1.04 |
| 2013-2019 | 84 | -0.14 | -0.16 | 0.69 |
| 2020-2026 | 78 | -0.03 | -0.02 | 0.74 |

**From 2008 onward the two series agree to within about a month, usually far
less.** Median difference across the whole overlap is +0.011 months. That is the
external check the WAM pipeline never had, and it passes for the entire modern
period.

### The 2001-2007 gap is systematic, not noise

A stable +2.9 month bias in one direction across 84 consecutive months, decaying
to zero by 2008, is a definitional difference. **Hypothesis, not yet confirmed:
callable bonds.** `wam.model_call_dates` is `false` — our calculation matures
callables at FINAL maturity. Treasury may use the call date. The 30-year bonds
issued through 1984 were callable at 25 years, so callables were outstanding
through roughly 2009 and gone thereafter, which matches the timing of the bias
and its decay almost exactly.

That is a testable claim: isolate the callable securities in `mspd_table_3_market`
for 2002, recompute WAM at call dates, and see whether the gap closes. Until that
is done it stays a hypothesis with a good fit, not a finding.

### What it means for the score

The published score starts 2007-01, so only its first year sits in the biased
era. WAM enters the score as a 12-month CHANGE, and a roughly constant offset
cancels in a difference — but the offset does not stay constant, it decays from
about +2.7 to about -0.3 across 2007-2008. That decay does not cancel: it adds up
to roughly three months of spurious WAM decline to our 12-month trend over that
window, which reads as extra shortening in 2008-2009.

Material for those two years specifically, immaterial from 2010 on. It should be
resolved before the 2008-2009 readings are used to argue anything.

## Testing the callable hypothesis: it explains about a third

Run through `build_wam`'s exact path — full-history fetch, `parse_endpoint`,
`normalize_securities_detail`, `wam_input(basis="PAR")` — the 2002-03 security
set is 176 securities weighting $3,041.6bn, WAM **69.1 months** against
Treasury's 64. Gap **+5.1 months**.

Fifteen bonds issued before 1985 with ~30-year terms are outstanding, **$79.4bn,
2.61% of par**, averaging 9.8 years to final maturity. Maturing them at the call
date (25 years) instead moves WAM by **−1.57 months**.

| | months | gap vs Treasury |
|---|---|---|
| pipeline, final maturity | 69.1 | +5.1 |
| callables at call date | 67.5 | +3.5 |

**Callables explain about 31% of the gap.** The convention is a genuine
divergence worth fixing — `wam.model_call_dates: false` costs about a month and a
half in this period — but roughly 3.5 months remain unexplained. Candidates not
yet tested: whether Treasury's series excludes some class we include, and whether
the bill weighting differs (bills are reported at maturity value, and at $834bn
they are 27% of par).

### WITHDRAWN: there is no internal inconsistency

An earlier version of this section reported a 2.7-month gap between the committed
pipeline and a recomputation, and called it "the more serious finding". **That was
wrong.** Running the pipeline's exact path and diffing security-by-security gives
an identical answer: 176 rows, $3,041.6bn, 69.1 months, zero difference in every
class.

The recomputation was reading `amount_outstanding` straight off
`normalize_securities_detail` instead of going through `wam_input(basis="PAR")`,
which substitutes `amount_par`. That is precisely the guard `wam_input` exists to
enforce — its docstring says the caller has to state a basis and that the answer
differs by roughly the accretion share of TIPS — and bypassing it produced a
wrong number twice in this investigation.

Both failures had the same shape: reimplementing a step the pipeline already
does, and getting a plausible answer that was wrong. The first bypassed subtotal
handling and double-counted; the second bypassed the weighting basis. Neither
looked wrong on inspection. **Any future check of this kind should call the
pipeline's own functions rather than reproduce them**, which is what finally
produced a trustworthy number here.


## Bill weighting and class coverage: both refuted, callables confirmed

Tested across all 306 overlapping months rather than at one date, using the
pipeline's own frame. Mean difference, ours minus Treasury, in months:

| era | as-is | call dates | ex-TIPS | call + ex-TIPS |
|---|---|---|---|---|
| 2001-2007 | +2.73 | **+1.64** | -1.51 | -2.65 |
| 2008-2012 | -0.32 | -0.39 | -3.98 | -4.05 |
| 2013-2019 | -0.14 | -0.14 | -2.94 | -2.94 |
| 2020-2026 | -0.03 | -0.03 | -1.41 | -1.41 |

**TIPS exclusion is refuted.** It looked promising at 2002-03, where dropping
TIPS moved WAM -3.6 months and landed within a month of Treasury's figure. Across
the full history it is decisively wrong: it degrades every era, pushing 2008-2012
from -0.32 to -3.98, and the share of months agreeing within half a month falls
from 61% to 8%. Treasury includes TIPS. The single-date result was a coincidence,
and testing one month would have produced a confident wrong answer.

**Bill weighting is refuted.** Bills are 27% of par and contribute 0.63 of the
69.1 months. Closing a 5.11-month gap by reweighting them would require carrying
bills at about 33% of par instead of 27% — a 30% over-weight with no basis in any
convention. Not a candidate.

**Callables are confirmed as a partial explanation.** Call-date treatment improves
2001-2007 from +2.73 to +1.64 — about 40% of that era's bias — and is essentially
neutral everywhere else (-0.32 to -0.39, then unchanged). A correction that acts
only where the problem is and costs nothing where there is no problem is the
signature of a real effect rather than a fitted one.

Note the composition that makes this plausible: bonds are 22% of par and 67% of
WAM (212.6 months average maturity against 2.3 for bills), so a bond-only
convention has leverage far beyond its weight.

### What remains

About **1.6 months** of the 2001-2007 bias is still unexplained after callables.
Untested: whether the 25-year call assumption holds for every one of the fifteen
bonds, and whether any non-bond securities of that era carried call provisions.

### Recommendation

Set `wam.model_call_dates: true`. It is a real divergence from Treasury,
measurably corrects the era it affects, and does no harm to the rest of the
series. The residual should be recorded rather than chased — the modern period,
which is what the score actually uses, already agrees to within a tenth of a
month.
