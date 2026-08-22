"""Run the backtest against the processed store and publish the result.

Answers one question: does what the sovereign DOES precede what the market
DEMANDS? Signals are quantity-only — bill share trend, incremental bill funding,
coupon restraint, and their composite. Outcomes are market prices the signals do
not contain: the 10y ACM term premium, long-end auction stress, and WAM.

Using the full six-factor score as the signal would be circular: it contains the
term premium trend and auction stress, so predicting them from it measures an
input against itself. That is the single most likely way to manufacture a
positive result here, so the full score is deliberately excluded rather than
reported alongside.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import pandas as pd
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.analysis.backtest import run  # noqa: E402

PROCESSED = REPO_ROOT / "data" / "processed"
OUT_DIR = REPO_ROOT / "docs" / "backtest"

QUANTITY_FACTORS = ["bill_share_trend", "incremental_bill_funding", "coupon_restraint"]


def load_signals_and_outcomes() -> tuple[dict, dict, pd.DataFrame]:
    score = pd.read_parquet(PROCESSED / "score.parquet")
    score["p"] = pd.PeriodIndex(score["period"], freq="M")
    score = score.set_index("p").sort_index()

    rank_cols = [c for c in score.columns if c.startswith("rank_")]
    ranks = score[rank_cols].rename(columns=lambda c: c[len("rank_"):])

    signals = {name: ranks[name].dropna() for name in QUANTITY_FACTORS if name in ranks}
    # The composite of the three, equally weighted. Not the published score:
    # that one contains the outcomes.
    present = [n for n in QUANTITY_FACTORS if n in ranks]
    if present:
        signals["quantity_composite"] = ranks[present].mean(axis=1).dropna()

    tp = pd.read_parquet(PROCESSED / "term_premium.parquet")
    tp10 = tp[tp["maturity"].astype(str) == "10Y"].set_index("date")["value"].sort_index()
    tp10 = tp10.resample("ME").last()
    tp10.index = tp10.index.to_period("M")

    stress = pd.read_parquet(PROCESSED / "long_end_stress.parquet")
    stress = stress.set_index("date")["long_end_stress"].sort_index().resample("ME").last()
    stress.index = stress.index.to_period("M")

    wam = pd.read_parquet(PROCESSED / "wam.parquet")
    wam_years = wam.set_index(
        pd.PeriodIndex(pd.to_datetime(wam["observation_date"]), freq="M")
    )["wam_years"].sort_index()

    # Kim-Wright, an INDEPENDENTLY estimated 10y term premium (FRED THREEFYTP10).
    # The one positive result this backtest produced rests on ACM, which is
    # revised data used as if it were real-time (Deviation D11). If the
    # relationship is an artefact of ACM's re-estimation rather than a fact about
    # the market, it should not survive against a different model of the same
    # quantity. Ingested for this purpose since Phase 1 and never used for it.
    rates = pd.read_parquet(PROCESSED / "rates.parquet")
    kw = rates[rates["series_id"] == "THREEFYTP10"].dropna(subset=["value"])
    kw = kw.set_index("date")["value"].sort_index().resample("ME").last()
    kw.index = kw.index.to_period("M")

    outcomes = {
        "term_premium_10y": tp10.dropna(),
        "term_premium_10y_kim_wright": kw.dropna(),
        "long_end_auction_stress": stress.dropna(),
        # Negated so that HIGHER always means MORE duration stress, matching the
        # signals' orientation. A falling WAM is shortening.
        "wam_shortening": (-wam_years).dropna(),
    }
    return signals, outcomes, ranks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--horizons", type=int, nargs="+", default=[3, 6, 12])
    args = ap.parse_args()

    signals, outcomes, ranks = load_signals_and_outcomes()
    print(f"signals: {list(signals)}")
    print(f"outcomes: {list(outcomes)}")
    print(f"horizons: {args.horizons}  ->  "
          f"{len(signals) * len(outcomes) * len(args.horizons)} tests\n", flush=True)

    # The FULL six-factor matrix: D6's promise is about the score's composition,
    # not about the subset used as signals here.
    report = run(signals, outcomes, horizons=tuple(args.horizons),
                 ranks=ranks, draws=args.draws)

    frame = report.to_frame().sort_values("ic", key=abs, ascending=False)
    print(frame.to_string(index=False))
    hits = frame[frame.excludes_zero]
    print(f"\n{len(hits)} of {report.n_tests} tests have a bootstrap interval "
          f"excluding zero.")
    if len(hits):
        expected = 0.05 * report.n_tests
        print(f"  (at 95%, about {expected:.1f} of {report.n_tests} would be "
              "expected by chance alone)")
        print(hits.to_string(index=False))

    print("\nfactor correlations (Spearman, on the ranks the score combines) — "
          "the matrix Deviation D6 promised:")
    print(report.factor_correlations.round(2).to_string())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT_DIR / "information_coefficients.csv", index=False)
    report.factor_correlations.round(4).to_csv(OUT_DIR / "factor_correlations.csv")
    (OUT_DIR / "summary.json").write_text(json.dumps({
        "n_tests": report.n_tests,
        "n_excluding_zero": int(len(hits)),
        "expected_by_chance_at_95pct": round(0.05 * report.n_tests, 2),
        "signals": list(signals),
        "outcomes": list(outcomes),
        "horizons": args.horizons,
        "bootstrap_draws": args.draws,
        "note": "Signals are quantity-only by construction; the full score "
                "contains two of the three outcomes and would be circular.",
    }, indent=2), encoding="utf-8")
    print(f"\n→ {OUT_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
