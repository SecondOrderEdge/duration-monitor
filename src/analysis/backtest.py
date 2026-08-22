"""Does the score carry forward information, or only describe the present?

The monitor's thesis is that a sovereign shifting its financing toward bills is
followed by the market demanding more to hold duration. That is a claim about
SEQUENCE, and nothing in the pipeline has tested it. Several live choices cite a
backtest that did not exist: the D6 weighting cites a factor correlation matrix
it promises to publish, and `duration_shift_score_bands` carries
`validated_by_backtest` on the strength of an ordering check done by hand.

Three design constraints, each of which can manufacture a positive result:

**Circularity.** The full score CONTAINS the 10y term premium trend and auction
stress. Using it to predict future term premium is partly measuring the
autocorrelation of an input against itself. Every forward test here therefore
uses the QUANTITY-ONLY subscore — what the sovereign did — against market
outcomes it does not contain. That is also the sharper version of the thesis.

**Overlapping windows.** A 12-month forward change sampled monthly reuses eleven
months of data between consecutive observations, so residuals are strongly
autocorrelated and an ordinary t-statistic is badly overstated. Significance here
comes from a circular block bootstrap with the block length tied to the horizon,
which preserves that dependence instead of assuming it away.

**Multiple testing.** Three signals x three outcomes x three horizons is
twenty-seven chances to find something. The count of tests run is reported
alongside the results, so a single striking number can be read against how many
were drawn.

Point-in-time throughout: the score is already built from trailing percentile
ranks and expanding weights (Deviation D1), and nothing here reaches forward
except the outcome being predicted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_HORIZONS = (3, 6, 12)


@dataclass
class ICResult:
    """One signal against one outcome at one horizon."""

    signal: str
    outcome: str
    horizon: int
    ic: float
    n: int
    ci_low: float
    ci_high: float
    block_length: int
    note: str = ""

    @property
    def significant(self) -> bool:
        """Whether the bootstrap interval excludes zero.

        Deliberately a property rather than a stored flag: it is a reading of the
        interval, not an independent fact, and storing it invites reporting it
        without the interval it came from.
        """
        return (self.ci_low > 0) or (self.ci_high < 0)


@dataclass
class BacktestReport:
    results: list[ICResult] = field(default_factory=list)
    n_tests: int = 0
    factor_correlations: pd.DataFrame | None = None

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"signal": r.signal, "outcome": r.outcome, "horizon_months": r.horizon,
             "ic": round(r.ic, 4), "n": r.n,
             "ci_low": round(r.ci_low, 4), "ci_high": round(r.ci_high, 4),
             "excludes_zero": r.significant, "block_length": r.block_length,
             "note": r.note}
            for r in self.results
        ])


def forward_change(series: pd.Series, horizon: int) -> pd.Series:
    """Change in `series` over the NEXT `horizon` periods, indexed at the start.

    Indexed at the start deliberately: the value at t is what happened AFTER t,
    so pairing it with a signal at t is a forward test by construction and cannot
    accidentally become a contemporaneous one.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    complete = series.sort_index()
    return complete.shift(-horizon) - complete


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Rank correlation, computed directly so ties are handled the same way as
    the percentile layer does rather than by whichever scipy default applies."""
    if len(a) < 3:
        return float("nan")
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denom = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / denom) if denom > 0 else float("nan")


def block_bootstrap_ci(
    signal: np.ndarray,
    outcome: np.ndarray,
    *,
    block_length: int,
    draws: int = 2000,
    alpha: float = 0.05,
    seed: int = 20260821,
) -> tuple[float, float]:
    """Confidence interval for a rank correlation under serial dependence.

    Circular block bootstrap: resample contiguous blocks so that the
    autocorrelation created by overlapping forward windows survives into the
    null. Sampling individual observations independently would destroy exactly
    the dependence that makes the naive interval wrong, and would produce a
    tight interval around a number that deserves a wide one.
    """
    n = len(signal)
    if n < 3 or block_length < 1:
        return (float("nan"), float("nan"))
    block_length = min(block_length, n)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_length))

    stats = np.empty(draws)
    for draw in range(draws):
        starts = rng.integers(0, n, size=n_blocks)
        idx = np.concatenate([
            (np.arange(start, start + block_length) % n) for start in starts
        ])[:n]
        stats[draw] = _spearman(signal[idx], outcome[idx])
    stats = stats[~np.isnan(stats)]
    if not len(stats):
        return (float("nan"), float("nan"))
    return (float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2)))


def information_coefficient(
    signal: pd.Series,
    outcome_level: pd.Series,
    *,
    horizon: int,
    signal_name: str = "signal",
    outcome_name: str = "outcome",
    draws: int = 2000,
) -> ICResult:
    """Rank correlation between a signal at t and the outcome's change after t."""
    forward = forward_change(outcome_level, horizon)
    joined = pd.concat([signal.rename("s"), forward.rename("f")], axis=1).dropna()
    if len(joined) < 12:
        return ICResult(signal_name, outcome_name, horizon, float("nan"),
                        len(joined), float("nan"), float("nan"), horizon,
                        note="fewer than 12 usable observations")

    a = joined["s"].to_numpy(dtype=float)
    b = joined["f"].to_numpy(dtype=float)
    ic = _spearman(a, b)
    # Block length is the horizon: that is exactly how many observations share
    # data through the overlapping forward window.
    lo, hi = block_bootstrap_ci(a, b, block_length=horizon, draws=draws)
    return ICResult(signal_name, outcome_name, horizon, ic, len(joined), lo, hi, horizon)


def factor_correlations(ranks: pd.DataFrame, *, method: str = "spearman") -> pd.DataFrame:
    """The matrix Deviation D6 promised to publish and never did.

    Spearman on the percentile ranks the score actually combines, not on the raw
    factors — the ranks are what the weighting sees.
    """
    return ranks.corr(method=method)


def run(
    signals: dict[str, pd.Series],
    outcomes: dict[str, pd.Series],
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    ranks: pd.DataFrame | None = None,
    draws: int = 2000,
) -> BacktestReport:
    """Every signal against every outcome at every horizon, counted."""
    report = BacktestReport()
    for signal_name, signal in signals.items():
        for outcome_name, outcome in outcomes.items():
            for horizon in horizons:
                report.results.append(information_coefficient(
                    signal, outcome, horizon=horizon,
                    signal_name=signal_name, outcome_name=outcome_name, draws=draws,
                ))
    report.n_tests = len(report.results)
    if ranks is not None:
        report.factor_correlations = factor_correlations(ranks)
    return report
