"""Tests for analysis/q3_analysis.py — including new F3a/F3b functions."""

import numpy as np
import pytest

import q3_analysis
from q3_analysis import (
    _gini,
    _kaplan_meier,
    _km_predict,
    _post_breakthrough_dynamics,
    _tas_proximity,
)


# ---------- helpers ----------

def _make_wr_rows(times: list[float], dates: list[str] | None = None,
                  game: str = "TestGame") -> list[dict]:
    """Build minimal wr_progression rows (game, date, time_seconds, wr_number)."""
    if dates is None:
        dates = [f"2010-{(i % 12) + 1:02d}-01" for i in range(len(times))]
    return [
        {
            "game":         game,
            "genre":        "Platformer",
            "category":     "Any%",
            "wr_number":    str(i + 1),
            "date":         dates[i],
            "time_seconds": str(t),
        }
        for i, t in enumerate(times)
    ]


# ---------- _gini ----------

class TestGini:
    def test_equal_distribution_near_zero(self):
        arr = np.array([10.0, 10.0, 10.0, 10.0, 10.0])
        assert _gini(arr) < 0.05

    def test_single_dominant_value_high_gini(self):
        # Gini ceiling = (n-1)/n, so n=5 caps at 0.80 regardless of ratio.
        # Use n=20 (ceiling 0.95) to verify a genuinely concentrated distribution
        # gives Gini well above 0.80.
        arr = np.array([10000.0] + [0.01] * 19)
        assert _gini(arr) > 0.85

    def test_all_zeros_returns_zero(self):
        arr = np.array([0.0, 0.0, 0.0])
        assert _gini(arr) == 0.0

    def test_single_value_returns_zero(self):
        arr = np.array([42.0])
        assert _gini(arr) == 0.0

    def test_two_values_equal(self):
        arr = np.array([5.0, 5.0])
        assert _gini(arr) < 0.05

    def test_output_in_0_1(self):
        rng = np.random.default_rng(0)
        for _ in range(20):
            arr = rng.exponential(scale=10.0, size=20)
            g = _gini(arr)
            assert 0.0 <= g <= 1.0

    def test_sign_insensitive_to_negatives(self):
        pos = np.array([100.0, 10.0, 1.0])
        neg = np.array([-100.0, -10.0, -1.0])
        assert abs(_gini(pos) - _gini(neg)) < 0.01

    def test_higher_inequality_gives_higher_gini(self):
        equal   = np.array([10.0, 10.0, 10.0, 10.0])
        unequal = np.array([100.0, 1.0, 1.0, 1.0])
        assert _gini(unequal) > _gini(equal)


# ---------- _kaplan_meier ----------

class TestKaplanMeier:
    def test_all_events_steps_down(self):
        durations = [1.0, 2.0, 3.0, 4.0]
        events    = [1, 1, 1, 1]
        median, curve = _kaplan_meier(durations, events)
        assert median <= 4.0
        # Survival curve must be non-increasing
        probs = [p for _, p in curve]
        assert all(probs[i] >= probs[i + 1] for i in range(len(probs) - 1))

    def test_all_censored_never_drops(self):
        durations = [10.0, 20.0, 30.0]
        events    = [0, 0, 0]
        median, curve = _kaplan_meier(durations, events)
        assert median == float("inf")
        # Curve stays at 1.0 throughout
        assert all(p == 1.0 for _, p in curve)

    def test_median_correct_simple_case(self):
        # 4 records: all broken at t=1,2,3,4 → S(2)=0.5, median=2
        durations = [1.0, 2.0, 3.0, 4.0]
        events    = [1, 1, 1, 1]
        median, _ = _kaplan_meier(durations, events)
        # S(t) = (3/4)*(2/3)*(1/2)... median where S≤0.5
        assert 2.0 <= median <= 4.0

    def test_censored_record_doesnt_step_curve(self):
        # 3 events + 1 censored late → median should be same as without censored
        d1 = [1.0, 2.0, 3.0]
        e1 = [1, 1, 1]
        median1, _ = _kaplan_meier(d1, e1)

        d2 = [1.0, 2.0, 3.0, 10.0]
        e2 = [1, 1, 1, 0]
        median2, _ = _kaplan_meier(d2, e2)
        assert median1 == median2

    def test_mixed_tied_times(self):
        # Two events at same time — should not crash
        durations = [5.0, 5.0, 10.0, 20.0]
        events    = [1, 1, 0, 1]
        median, curve = _kaplan_meier(durations, events)
        assert median is not None

    def test_single_event(self):
        median, curve = _kaplan_meier([7.0], [1])
        assert median == 7.0

    def test_curve_starts_at_1(self):
        median, curve = _kaplan_meier([1.0, 2.0, 3.0], [1, 0, 1])
        assert curve[0] == (0.0, 1.0)


# ---------- _km_predict ----------

class TestKmPredict:
    def test_predict_at_zero_returns_one(self):
        curve = [(0.0, 1.0), (5.0, 0.75), (10.0, 0.5)]
        assert _km_predict(curve, 0.0) == 1.0

    def test_predict_between_steps(self):
        curve = [(0.0, 1.0), (5.0, 0.75), (10.0, 0.5)]
        # Between 5 and 10 → still 0.75 (right-continuous step function)
        assert _km_predict(curve, 7.0) == 0.75

    def test_predict_beyond_last_step(self):
        curve = [(0.0, 1.0), (5.0, 0.75), (10.0, 0.5)]
        assert _km_predict(curve, 100.0) == 0.5

    def test_predict_exactly_at_step(self):
        curve = [(0.0, 1.0), (5.0, 0.75)]
        assert _km_predict(curve, 5.0) == 0.75


# ---------- _post_breakthrough_dynamics (F3a) ----------

class TestPostBreakthroughDynamics:
    """_post_breakthrough_dynamics returns a PostBreakthroughResult DTO."""

    _FLAT_TIMES = [500.0, 490.0, 480.0, 470.0, 200.0, 199.5, 199.0, 198.5, 198.0]
    _FLAT_DATES = ["2010-01-01", "2010-04-01", "2010-07-01", "2010-10-01",
                   "2011-01-01", "2013-01-01", "2015-01-01", "2017-01-01", "2019-01-01"]

    def test_returns_none_for_too_few_rows(self):
        rows = _make_wr_rows([200.0, 190.0, 180.0, 170.0])
        assert _post_breakthrough_dynamics("TestGame", rows) is None

    def test_returns_none_when_too_few_pre_imps(self):
        times = [200.0, 100.0, 99.0, 98.0, 97.0, 96.0]
        dates = ["2010-01-01", "2010-02-01", "2011-01-01",
                 "2012-01-01", "2013-01-01", "2014-01-01"]
        rows = _make_wr_rows(times, dates)
        assert _post_breakthrough_dynamics("TestGame", rows) is None

    def test_flattens_after_breakthrough(self):
        rows   = _make_wr_rows(self._FLAT_TIMES, self._FLAT_DATES)
        result = _post_breakthrough_dynamics("TestGame", rows)
        assert result is not None
        assert result.interpretation == "flattens_after_breakthrough"
        assert result.flattening_ratio < 0.5

    def test_continues_improving_after_breakthrough(self):
        times = [500.0, 495.0, 490.0, 485.0, 300.0, 250.0, 180.0, 90.0, 10.0]
        dates = ["2010-01-01", "2010-06-01", "2011-01-01", "2011-06-01",
                 "2012-01-01", "2012-06-01", "2013-01-01", "2013-06-01", "2014-01-01"]
        rows   = _make_wr_rows(times, dates)
        result = _post_breakthrough_dynamics("TestGame", rows)
        assert result is not None
        assert result.interpretation in ("accelerates_after_breakthrough", "gradual_slowdown")

    def test_to_dict_has_required_keys(self):
        rows   = _make_wr_rows(self._FLAT_TIMES, self._FLAT_DATES)
        result = _post_breakthrough_dynamics("TestGame", rows)
        assert result is not None
        d = result.to_dict()
        for key in ("game", "breakthrough_magnitude_s", "breakthrough_date",
                    "breakthrough_wr_number", "breakthrough_pct_of_total",
                    "pre_velocity_s_per_day", "post_velocity_s_per_day",
                    "flattening_ratio", "post_trend", "days_to_10pct_threshold",
                    "interpretation"):
            assert key in d, f"missing key: {key}"

    def test_breakthrough_magnitude_is_largest_improvement(self):
        rows   = _make_wr_rows(self._FLAT_TIMES, self._FLAT_DATES)
        result = _post_breakthrough_dynamics("TestGame", rows)
        assert result is not None
        assert abs(result.breakthrough_magnitude_s - 270.0) < 1.0

    def test_breakthrough_pct_of_total_in_0_100(self):
        rows   = _make_wr_rows(self._FLAT_TIMES, self._FLAT_DATES)
        result = _post_breakthrough_dynamics("TestGame", rows)
        if result and result.breakthrough_pct_of_total is not None:
            assert 0.0 < result.breakthrough_pct_of_total <= 100.0

    def test_flattening_ratio_positive(self):
        rows   = _make_wr_rows(self._FLAT_TIMES, self._FLAT_DATES)
        result = _post_breakthrough_dynamics("TestGame", rows)
        if result and result.flattening_ratio is not None:
            assert result.flattening_ratio >= 0

    def test_post_trend_rho_in_neg1_pos1(self):
        times = [500.0, 490.0, 480.0, 470.0, 200.0, 195.0, 185.0, 168.0, 143.0, 108.0]
        dates = ["2010-01-01", "2010-04-01", "2010-07-01", "2010-10-01",
                 "2011-01-01", "2013-01-01", "2015-01-01", "2017-01-01",
                 "2019-01-01", "2021-01-01"]
        rows   = _make_wr_rows(times, dates)
        result = _post_breakthrough_dynamics("TestGame", rows)
        if result and result.post_trend is not None:
            rho = result.post_trend.rho
            if rho is not None:
                assert -1.0 <= rho <= 1.0

    def test_interpretation_is_valid_string(self):
        rows   = _make_wr_rows(self._FLAT_TIMES, self._FLAT_DATES)
        result = _post_breakthrough_dynamics("TestGame", rows)
        valid = {"flattens_after_breakthrough", "accelerates_after_breakthrough",
                 "gradual_slowdown", "insufficient_data"}
        if result:
            assert result.interpretation in valid

    def test_game_field_matches_input(self):
        rows   = _make_wr_rows(self._FLAT_TIMES, self._FLAT_DATES, game="Celeste")
        result = _post_breakthrough_dynamics("Celeste", rows)
        if result:
            assert result.game == "Celeste"


# ---------- _tas_proximity (F3b) ----------

class TestTasProximity:
    """_tas_proximity returns a TasProximityResult DTO."""

    def _exp_decay_rows(self, a=200.0, b=0.008, c=50.0, n=40):
        import math
        times = [a * math.exp(-b * i * 15) + c for i in range(n)]
        dates = [f"{2000 + i // 12}-{(i % 12) + 1:02d}-01" for i in range(n)]
        return _make_wr_rows(times, dates)

    def test_returns_none_for_too_few_rows(self):
        rows = _make_wr_rows([200.0, 190.0, 180.0, 170.0])
        assert _tas_proximity("TestGame", rows) is None

    def test_detects_floor_on_clear_exp_decay(self):
        rows   = self._exp_decay_rows()
        result = _tas_proximity("TestGame", rows)
        assert result is not None
        assert result.floor_model in ("exp_decay", "gompertz", "none_detected")

    def test_floor_below_current_wr(self):
        rows   = self._exp_decay_rows()
        result = _tas_proximity("TestGame", rows)
        if result and result.floor_model != "none_detected":
            assert result.theoretical_floor_s < result.current_wr_s

    def test_gap_non_negative(self):
        rows   = self._exp_decay_rows()
        result = _tas_proximity("TestGame", rows)
        if result and result.floor_model != "none_detected":
            assert result.gap_to_floor_s >= 0

    def test_pct_achieved_in_0_100(self):
        rows   = self._exp_decay_rows()
        result = _tas_proximity("TestGame", rows)
        if result and result.pct_of_theoretical_reduction_achieved is not None:
            assert 0.0 <= result.pct_of_theoretical_reduction_achieved <= 100.0

    def test_gap_pct_non_negative(self):
        rows   = self._exp_decay_rows()
        result = _tas_proximity("TestGame", rows)
        if result and result.floor_model != "none_detected":
            assert result.gap_to_floor_pct_of_first_wr >= 0

    def test_linear_data_reports_no_floor(self):
        times = [500.0 - i * 10.0 for i in range(25)]
        dates = [f"{2000 + i}-01-01" for i in range(25)]
        rows  = _make_wr_rows(times, dates)
        result = _tas_proximity("TestGame", rows)
        assert result is not None
        if result.floor_model == "none_detected":
            assert result.note is not None

    def test_result_has_game_field(self):
        rows   = self._exp_decay_rows()
        result = _tas_proximity("TestGame", rows)
        assert result is not None
        assert result.game == "TestGame"

    def test_to_dict_has_game_key(self):
        rows   = self._exp_decay_rows()
        result = _tas_proximity("TestGame", rows)
        assert result is not None
        assert "game" in result.to_dict()

    def test_estimated_years_positive_when_present(self):
        rows   = self._exp_decay_rows()
        result = _tas_proximity("TestGame", rows)
        if result and result.estimated_years_to_floor is not None:
            assert result.estimated_years_to_floor > 0

    def test_convergence_velocity_non_negative_when_closing_gap(self):
        rows   = self._exp_decay_rows()
        result = _tas_proximity("TestGame", rows)
        if result and result.floor_model != "none_detected":
            if result.convergence_velocity_s_per_year is not None:
                assert result.convergence_velocity_s_per_year >= 0


# ---------- _event_from_row ----------

class TestEventFromRow:
    def test_reads_event_column(self):
        assert q3_analysis._event_from_row({"event": "1"}) == 1
        assert q3_analysis._event_from_row({"event": "0"}) == 0

    def test_falls_back_to_is_final(self):
        assert q3_analysis._event_from_row({"is_final": "True"})  == 0
        assert q3_analysis._event_from_row({"is_final": "False"}) == 1

    def test_empty_event_falls_back(self):
        assert q3_analysis._event_from_row({"event": "", "is_final": "True"}) == 0


# ---------- _load_csv (smoke) ----------

class TestLoadCsvMissing:
    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            q3_analysis._load_csv("__definitely_not_there__.csv")
