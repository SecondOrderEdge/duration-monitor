"""Config access, with the units conversion made explicit.

`config/thresholds.yaml` expresses money thresholds in MILLIONS — the unit MSPD
publishes in, and the unit a human reading the file thinks in. The processed
store holds SINGLE CURRENCY UNITS, per the schema decision that keeps Phase 3
from inheriting a units bug.

Those two facts are individually sensible and jointly a trap: a threshold of
25000 applied to a store holding 2.7e13 masks nothing at all, and the resulting
chart is populated, plausible and wrong. So the conversion happens here, once,
behind a name that says which unit it returns, rather than as a bare `* 1e6`
wherever someone remembers it.

The `_musd` suffix in the config is the load-bearing part: it marks the unit at
the point of definition, so a reader does not have to trace the value to know it.

Calculations never call this. They take explicit parameters, which is what makes
them testable against hand-computed fixtures — config is resolved by the caller
(the pipeline, or the app) and passed in.
"""

from __future__ import annotations

import functools
import pathlib

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "config"

MILLIONS = 1_000_000


@functools.lru_cache(maxsize=None)
def load(name: str) -> dict:
    """Load a config file by stem, e.g. `load("thresholds")`."""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"no config/{name}.yaml; available: "
            f"{sorted(p.stem for p in CONFIG_DIR.glob('*.yaml'))}"
        )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def min_abs_denominator(freq: str = "M") -> float:
    """Issuance-ratio denominator floor, in SINGLE CURRENCY UNITS.

    Converted from the `_musd` value in thresholds.yaml. Passing the raw config
    number to `incremental_bill_funding` against the processed store would set a
    floor a million times too low, which silently disables the debt-ceiling guard
    of Deviation D5 — the single most likely source of a false positive here.
    """
    key = {
        "M": "min_abs_denominator_monthly_musd",
        "Q": "min_abs_denominator_quarterly_musd",
    }.get(freq)
    if key is None:
        raise ValueError(f"no denominator floor configured for freq {freq!r}")
    return float(load("thresholds")["issuance"][key]) * MILLIONS


def bill_share_reference_band() -> tuple[float, float]:
    """TBAC's recommended bill share range, as fractions (Deviation D10)."""
    low, high = load("thresholds")["reference_levels"]["bill_share_recommended_band"]
    return float(low), float(high)


def reconciliation_tolerance_pct() -> float:
    return float(load("thresholds")["validation"]["reconciliation_tolerance_pct"])
