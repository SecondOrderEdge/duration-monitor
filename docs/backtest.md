# Does the score carry forward information?

The monitor's thesis is a claim about sequence: a sovereign shifting its
financing toward bills is followed by the market demanding more to hold duration.
Nothing tested it until now, while several live choices cited a backtest that did
not exist.

## Design

**Signals are quantity-only.** The published six-factor score CONTAINS the 10y
term premium trend and long-end auction stress. Predicting those from it measures
an input against itself. Every test here uses what the sovereign DID — bill share
trend, incremental bill funding, coupon restraint, and their equal-weighted
composite — against market outcomes those signals do not contain. That is also
the sharper version of the thesis.

**Overlapping windows are handled, not assumed away.** A 12-month forward change
sampled monthly reuses eleven months between consecutive observations. Intervals
come from a circular block bootstrap with block length equal to the horizon, which
preserves that dependence. An ordinary t-statistic here would be badly overstated.

**Every test is counted.** 4 signals x 3 outcomes x 3 horizons = **36 tests**, of
which about **1.8 would be expected to exclude zero by chance** at 95%.

## Result: 9 of 36 exclude zero

| signal | outcome | horizon | IC | 95% interval |
|---|---|---|---|---|
| coupon_restraint | term premium 10y | 6m | **0.256** | 0.025 to 0.442 |
| quantity_composite | term premium 10y | 6m | **0.250** | 0.028 to 0.419 |
| bill_share_trend | term premium 10y | 6m | **0.249** | 0.012 to 0.442 |
| coupon_restraint | term premium 10y | 3m | 0.202 | 0.012 to 0.355 |
| quantity_composite | wam shortening | 3m | 0.254 | 0.072 to 0.407 |
| quantity_composite | wam shortening | 6m | 0.251 | 0.001 to 0.457 |
| incremental_bill_funding | wam shortening | 3m | 0.234 | 0.063 to 0.386 |
| incremental_bill_funding | wam shortening | 6m | 0.219 | 0.014 to 0.404 |
| coupon_restraint | wam shortening | 3m | 0.205 | 0.016 to 0.371 |

**The thesis survives, weakly.** Quantity signals lead the 10y term premium at
three and six months with information coefficients around 0.20-0.26. Nine hits
against 1.8 expected by chance is well beyond noise, and the term-premium results
are the ones the thesis actually predicts.

Read the intervals, not the point estimates. Several barely clear zero — the
6-month WAM result runs 0.001 to 0.457. An IC of 0.25 means the signal explains
roughly 6% of rank variance. This is a real but modest edge, not a timing tool.

The WAM results are the least interesting of the three: issuance mix and the
maturity of the outstanding stock are mechanically linked, so a quantity signal
leading WAM shortening is closer to arithmetic than to a market reaction.

## The clean negative: auction stress

**Every** signal against long-end auction stress, at every horizon, returns an IC
between **-0.046 and +0.035**. Not one interval excludes zero. Twelve tests, no
signal.

Bill-heavy financing does not precede weaker long-end auctions in this sample.
That is the half of the thesis about the market refusing duration, and on this
evidence it is unsupported. The term premium responds; the auction does not.

Worth stating plainly because it bears on the regime classifier, which requires
auction-stress corroboration at its most severe level. That threshold is asking
for confirmation from a series that has shown no forward relationship to the
quantity signals driving the score.

## The factor correlation matrix Deviation D6 promised

Spearman, on the point-in-time ranks the score actually combines:

| | bill_share | incr_bill | wam | coupon | term_prem | auction |
|---|---|---|---|---|---|---|
| bill_share_trend | 1.00 | 0.01 | 0.80 | **0.93** | 0.21 | 0.12 |
| incremental_bill_funding | 0.01 | 1.00 | -0.03 | -0.02 | -0.14 | -0.02 |
| wam_trend | 0.80 | -0.03 | 1.00 | 0.76 | 0.09 | 0.12 |
| coupon_restraint | **0.93** | -0.02 | 0.76 | 1.00 | 0.25 | 0.14 |
| term_premium_10y_trend | 0.21 | -0.14 | 0.09 | 0.25 | 1.00 | -0.04 |
| long_end_auction_stress | 0.12 | -0.02 | 0.12 | 0.14 | -0.04 | 1.00 |

**This partly contradicts the D6 note in `config/factor_weights.yaml`.** That note
says bill share trend, WAM trend and coupon restraint are "mutually correlated
0.91-0.97" — measured here at 0.93, 0.80 and 0.76, so the range is wider and
lower than stated but the substance holds. It also says incremental bill funding
and coupon restraint "are the SAME number at matched horizons". At the horizons
the score actually uses they correlate **-0.02**: incremental bill funding is
orthogonal to everything, and is the most independent quantity factor in the set.

The correlation-adjusted weighting is doing the right thing regardless — it
derives weights from this structure rather than assuming one — but the note
justifying it describes a relationship the score does not contain. It should be
corrected to match what is measured.

## Known limitation (Deviation D11)

Term premium history uses today's ACM vintage as if it were real-time. ACM is
re-estimated retroactively and point-in-time vintages are not freely available.
This cannot be fixed, only disclosed: the term-premium results above are computed
on revised data, and a real-time investor would not have seen these values.
`THREEFYTP10` (Kim-Wright) is ingested as an independent cross-check and has not
yet been used for one.

## Reproducing

    python scripts/backtest.py --draws 2000

Outputs `docs/backtest/information_coefficients.csv`,
`factor_correlations.csv` and `summary.json`.
