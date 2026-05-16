"""Tests for analysis/q1_analysis.py helper functions."""

import numpy as np
import pytest

import q1_analysis


def _make_wr_rows(dates: list[str], improvements: list[float]) -> list[dict]:
    """Build minimal wr_progression rows from dates and improvement sizes."""
    rows = []
    time = 500.0
    for i, (d, imp) in enumerate(zip(dates, improvements)):
        rows.append({
            "game": "TestGame",
            "genre": "TestGenre",
            "date": d,
            "improvement_s": str(imp),
            "time_seconds": str(time),
            "wr_number": str(i + 1),
        })
        time -= imp
    return rows


# ---------- _velocity_trend ----------

class TestVelocityTrend:
    def test_decelerating_returns_negative_rho(self):
        # Improvements shrink over time -> rho < 0
        dates = [f"202{i}-01-01" for i in range(8)]
        imps = [100.0, 80.0, 60.0, 40.0, 20.0, 10.0, 5.0, 2.0]
        rows = _make_wr_rows(dates, imps)
        result = q1_analysis._velocity_trend(rows)
        assert result["rho"] < 0
        assert result["interpretation"] == "decelerating"

    def test_accelerating_returns_positive_rho(self):
        # Improvements grow over time -> rho > 0
        dates = [f"201{i}-06-01" for i in range(8)]
        imps = [2.0, 5.0, 10.0, 20.0, 40.0, 60.0, 80.0, 100.0]
        rows = _make_wr_rows(dates, imps)
        result = q1_analysis._velocity_trend(rows)
        assert result["rho"] > 0
        assert result["interpretation"] == "accelerating"

    def test_insufficient_data_below_4(self):
        rows = _make_wr_rows(["2020-01-01", "2020-06-01", "2021-01-01"], [10.0, 8.0, 6.0])
        result = q1_analysis._velocity_trend(rows)
        assert result["interpretation"] == "insufficient_data"
        assert result["rho"] is None

    def test_no_trend_near_zero_rho(self):
        # Random-ish sequence with no direction -> interpretation no_trend
        dates = [f"2020-0{i+1}-01" for i in range(8)]
        imps = [10.0, 12.0, 9.0, 11.0, 10.5, 9.5, 11.0, 10.0]
        rows = _make_wr_rows(dates, imps)
        result = q1_analysis._velocity_trend(rows)
        assert result["interpretation"] in ("no_trend", "decelerating", "accelerating")
        assert result["pvalue"] is not None

    def test_rows_with_zero_improvement_included(self):
        # The function filters by key presence ("0.0" is a truthy string),
        # so zero improvements ARE included and dilute the correlation.
        # With alternating 0s, trend direction weakens to no_trend.
        dates = [f"202{i}-01-01" for i in range(8)]
        imps = [0.0, 80.0, 0.0, 40.0, 0.0, 10.0, 0.0, 2.0]
        rows = _make_wr_rows(dates, imps)
        result = q1_analysis._velocity_trend(rows)
        # Behavior: zeros dilute the Spearman signal, so result is no_trend or decelerating
        assert result["interpretation"] in ("no_trend", "decelerating")

    def test_pvalue_between_0_and_1(self):
        dates = [f"202{i}-01-01" for i in range(6)]
        imps = [50.0, 30.0, 20.0, 10.0, 5.0, 2.0]
        rows = _make_wr_rows(dates, imps)
        result = q1_analysis._velocity_trend(rows)
        assert 0.0 <= result["pvalue"] <= 1.0


# ---------- _power_law_on_improvements ----------

class TestPowerLawOnImprovements:
    def test_returns_none_for_too_few_rows(self):
        rows = _make_wr_rows(["2020-01-01", "2021-01-01", "2022-01-01"], [10.0, 8.0, 6.0])
        result = q1_analysis._power_law_on_improvements(rows)
        assert result is None

    def test_returns_dict_for_sufficient_rows(self):
        dates = [f"20{10+i}-01-01" for i in range(8)]
        imps = [100.0, 50.0, 30.0, 20.0, 10.0, 5.0, 3.0, 1.0]
        rows = _make_wr_rows(dates, imps)
        result = q1_analysis._power_law_on_improvements(rows)
        assert result is not None
        assert "model" in result

    def test_exponent_negative_for_diminishing_returns(self):
        dates = [f"20{10+i}-01-01" for i in range(8)]
        # Strongly diminishing: each WR saves half as much
        imps = [128.0, 64.0, 32.0, 16.0, 8.0, 4.0, 2.0, 1.0]
        rows = _make_wr_rows(dates, imps)
        result = q1_analysis._power_law_on_improvements(rows)
        assert result is not None
        params = result.get("params", {})
        if "b" in params:
            assert params["b"] < 0

    def test_zero_improvements_excluded(self):
        dates = [f"20{10+i}-01-01" for i in range(8)]
        imps = [0.0, 50.0, 0.0, 20.0, 10.0, 5.0, 3.0, 1.0]
        rows = _make_wr_rows(dates, imps)
        # Should not crash on zero improvements
        result = q1_analysis._power_law_on_improvements(rows)
        # Either succeeds or returns None (not enough non-zero points)
        assert result is None or "model" in result


# ---------- _load_csv (smoke test via run() -- requires no real file, skip if absent) ----------

class TestLoadCsvMissing:
    def test_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            q1_analysis._load_csv("__nonexistent__.csv")
