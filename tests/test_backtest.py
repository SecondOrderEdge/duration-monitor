"""The backtest's own guards.

A backtest is the one component that can talk itself into a result, so the tests
here are mostly about the ways it could report something that is not there:
looking forward when it should not, treating overlapping windows as independent,
and losing count of how many tests were run.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.analysis.backtest import (
    block_bootstrap_ci,
    factor_correlations,
    forward_change,
    information_coefficient,
    run,
)


def _months(n: int, start: str = "2010-01") -> pd.PeriodIndex:
    return pd.period_range(start, periods=n, freq="M")


def test_forward_change_is_indexed_at_the_start_of_the_window():
    """The value at t must be what happened AFTER t, or the test is not forward."""
    s = pd.Series([1.0, 2.0, 4.0, 7.0], index=_months(4))
    f = forward_change(s, 1)
    assert f.iloc[0] == 1.0 and f.iloc[1] == 2.0 and f.iloc[2] == 3.0
    assert pd.isna(f.iloc[-1]), "the last period has no future and must be NaN"


def test_forward_change_never_looks_backward():
    """A sign slip here would silently turn the whole exercise contemporaneous."""
    s = pd.Series(np.arange(10, dtype=float), index=_months(10))
    assert (forward_change(s, 3).dropna() > 0).all()


def test_a_zero_or_negative_horizon_is_refused():
    with pytest.raises(ValueError):
        forward_change(pd.Series([1.0, 2.0], index=_months(2)), 0)


def test_a_perfect_forward_relationship_is_detected():
    rng = np.random.default_rng(0)
    idx = _months(160)
    signal = pd.Series(rng.normal(size=160), index=idx)
    # Outcome LEVEL constructed so that its next-period change IS the signal:
    # level[t] = sum(signal[:t]), hence level[t+1] - level[t] == signal[t]. No
    # extra shift — forward_change already does the aligning, and shifting again
    # would test a lag the construction does not contain.
    level = pd.Series(np.concatenate([[0.0], np.cumsum(signal.to_numpy()[:-1])]), index=idx)
    r = information_coefficient(signal, level, horizon=1, draws=300)
    assert r.ic > 0.9 and r.significant


def test_pure_noise_does_not_come_back_significant():
    rng = np.random.default_rng(7)
    idx = _months(200)
    signal = pd.Series(rng.normal(size=200), index=idx)
    level = pd.Series(np.cumsum(rng.normal(size=200)), index=idx)
    r = information_coefficient(signal, level, horizon=12, draws=400)
    assert not r.significant, f"noise reported significant: ic={r.ic:.3f}"


def test_the_bootstrap_widens_the_interval_versus_independent_sampling():
    """Overlapping windows create dependence; blocks must not assume it away.

    A block length of 1 IS independent sampling. If longer blocks did not widen
    the interval, the correction would be decorative.
    """
    rng = np.random.default_rng(3)
    x = np.cumsum(rng.normal(size=240))          # strongly serially dependent
    y = np.cumsum(rng.normal(size=240))
    lo1, hi1 = block_bootstrap_ci(x, y, block_length=1, draws=500)
    lo12, hi12 = block_bootstrap_ci(x, y, block_length=12, draws=500)
    assert (hi12 - lo12) > (hi1 - lo1)


def test_too_few_observations_returns_nan_with_a_reason_not_a_number():
    idx = _months(8)
    r = information_coefficient(pd.Series(np.arange(8.0), index=idx),
                                pd.Series(np.arange(8.0), index=idx),
                                horizon=3, draws=50)
    assert np.isnan(r.ic) and "fewer than 12" in r.note


def test_every_test_run_is_counted():
    """Twenty-seven chances to find something must be reported as twenty-seven."""
    idx = _months(120)
    rng = np.random.default_rng(1)
    sig = {f"s{i}": pd.Series(rng.normal(size=120), index=idx) for i in range(3)}
    out = {f"o{i}": pd.Series(np.cumsum(rng.normal(size=120)), index=idx) for i in range(3)}
    rep = run(sig, out, horizons=(3, 6, 12), draws=50)
    assert rep.n_tests == 27 and len(rep.to_frame()) == 27


def test_significance_is_derived_from_the_interval_not_stored_separately():
    idx = _months(120)
    r = information_coefficient(pd.Series(np.arange(120.0), index=idx),
                                pd.Series(np.arange(120.0), index=idx),
                                horizon=3, draws=100)
    assert r.significant == ((r.ci_low > 0) or (r.ci_high < 0))


def test_factor_correlations_are_computed_on_the_ranks_the_score_combines():
    ranks = pd.DataFrame({"a": [1.0, 2, 3, 4, 5], "b": [5.0, 4, 3, 2, 1],
                          "c": [1.0, 3, 2, 5, 4]})
    m = factor_correlations(ranks)
    assert m.loc["a", "b"] == pytest.approx(-1.0)
    assert list(m.columns) == ["a", "b", "c"]
