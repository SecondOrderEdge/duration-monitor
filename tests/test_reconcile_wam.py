"""Reading the published average-maturity grid, and differencing it against ours.

The trap is the sibling series. The SAME workbook carries "Average Length of
Marketable Interest-Bearing Public Debt", which measures debt held by PRIVATE
INVESTORS — a different population that moves with Federal Reserve holdings.
Picking a sheet by position rather than by its own title would read that one and
report a confident discrepancy in our pipeline that is really a definitional
mismatch.
"""

from __future__ import annotations

import io
import pathlib
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scripts.reconcile_wam import ReconciliationError, compare, find_series

TITLE = "Average Maturity of Treasury Marketable Securities--Total Outstanding (in months)"
LENGTH_TITLE = "Maturity Distribution and Average Length of Marketable Interest-Bearing Public Debt"


def _workbook(sheets: dict[str, list[list]]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, rows in sheets.items():
            pd.DataFrame(rows).to_excel(writer, sheet_name=name, index=False, header=False)
    return buf.getvalue()


def _grid(title: str = TITLE) -> list[list]:
    return [
        [title],
        [],
        ["Year", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        [2000, 68, 69, 67, 69, 70, 69, 69, 69, 69, 70, 70, 71],
        [2001, 66, 66, 65, 64, 64, 63, 63, 62, 62, 61, 61, 60],
    ]


def test_the_monthly_grid_is_read_into_a_series():
    series, title = find_series(_workbook({"Avg. mat. of debt outstanding": _grid()}))
    assert len(series) == 24
    assert series[pd.Period("2000-01", freq="M")] == 68
    assert series[pd.Period("2001-12", freq="M")] == 60
    assert "Avg. mat." in title


def test_the_private_investor_sheet_is_refused():
    """Average LENGTH is a different population. Reading it would report a
    definitional mismatch as an error in our pipeline."""
    with pytest.raises(ReconciliationError):
        find_series(_workbook({"Maturity dist. of debt out.": _grid(LENGTH_TITLE)}))


def test_the_right_sheet_is_chosen_when_both_are_present():
    payload = _workbook({
        "Maturity dist. of debt out.": _grid(LENGTH_TITLE),
        "Avg. mat. of debt outstanding": _grid(),
    })
    _, title = find_series(payload)
    assert "Avg. mat." in title


def test_the_header_row_is_found_by_content_not_by_offset():
    """These workbooks carry title blocks of varying height above the grid."""
    rows = [["Department of the Treasury"], ["Office of Debt Management"], [],
            [TITLE], [], []] + _grid()[2:]
    series, _ = find_series(_workbook({"Avg. mat. of debt outstanding": rows}))
    assert series[pd.Period("2000-01", freq="M")] == 68


def test_a_workbook_without_the_grid_raises_rather_than_returning_empty():
    payload = _workbook({"Notes": [["nothing useful here"]]})
    with pytest.raises(ReconciliationError):
        find_series(payload)


def test_units_are_converted_once_at_the_comparison():
    ours = pd.DataFrame({"observation_date": [pd.Timestamp("2000-01-31")],
                         "wam_years": [5.75]})
    published = pd.Series({pd.Period("2000-01", freq="M"): 68.0})
    joined = compare(ours, published)
    assert joined.loc[pd.Period("2000-01", freq="M"), "our_months"] == pytest.approx(69.0)
    assert joined.loc[pd.Period("2000-01", freq="M"), "difference_months"] == pytest.approx(1.0)


def test_sub_half_month_gaps_count_as_rounding():
    """Treasury publishes whole months; 0.4 of a month is not a discrepancy."""
    ours = pd.DataFrame({"observation_date": [pd.Timestamp("2000-01-31")],
                         "wam_years": [68.4 / 12]})
    joined = compare(ours, pd.Series({pd.Period("2000-01", freq="M"): 68.0}))
    assert bool(joined["within_rounding"].iloc[0])


def test_months_present_in_only_one_series_are_dropped_not_filled():
    ours = pd.DataFrame({"observation_date": [pd.Timestamp("2000-01-31"),
                                              pd.Timestamp("2030-01-31")],
                         "wam_years": [5.75, 6.0]})
    joined = compare(ours, pd.Series({pd.Period("2000-01", freq="M"): 68.0}))
    assert len(joined) == 1, "an inner join; no month is invented on either side"


# --------------------------------------------------------------------------- #
# The standing check
# --------------------------------------------------------------------------- #

def test_the_configured_limit_is_above_treasurys_rounding_floor():
    """Treasury publishes whole months, so anything at or under half a month is
    rounding. A limit below that would fire on arithmetic, not on drift."""
    import yaml

    cfg = yaml.safe_load(
        (pathlib.Path(__file__).resolve().parents[1] / "config" / "thresholds.yaml")
        .read_text(encoding="utf-8")
    )["validation"]["wam_vs_treasury"]
    assert cfg["max_median_abs_difference_months"] >= 0.5


def test_the_check_starts_after_the_known_callable_divergence():
    """2001-2007 carries an accepted +2.7 month gap from the callable convention.
    Judging from 2001 would make the check fire permanently on something already
    understood, which is how a check gets ignored."""
    import yaml

    cfg = yaml.safe_load(
        (pathlib.Path(__file__).resolve().parents[1] / "config" / "thresholds.yaml")
        .read_text(encoding="utf-8")
    )["validation"]["wam_vs_treasury"]
    assert pd.Period(str(cfg["judge_from"]), freq="M") >= pd.Period("2008-01", freq="M")
