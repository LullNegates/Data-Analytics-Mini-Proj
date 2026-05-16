"""Tests for analysis/f3b_tas_analysis.py — TAS vs human WR comparison."""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Ensure analysis/ is on the path (conftest.py does this, but explicit is safer)
import f3b_tas_analysis
from f3b_tas_analysis import (
    _build_gap_history,
    _gap_velocity,
    _analyse_game,
    _cross_game_summary,
)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.DTOs.f3b_dtos import TasComparisonResult, TasGapSnapshot


# ---------- helpers ----------

def _make_wr_rows(times: list[float], dates: list[str] | None = None,
                  game: str = "TestGame") -> list[dict]:
    if dates is None:
        dates = [f"2010-{(i % 12) + 1:02d}-01" for i in range(len(times))]
    return [
        {
            "game":         game,
            "genre":        "Platformer",
            "wr_number":    str(i + 1),
            "date":         dates[i],
            "time_seconds": str(t),
        }
        for i, t in enumerate(times)
    ]


def _make_tas_info(tas_time_s: float, source: str = "TestSource") -> dict:
    return {"tas_time_s": tas_time_s, "source": source, "confidence": "high"}


# ---------- _build_gap_history ----------

class TestBuildGapHistory:
    def test_length_matches_wr_count(self):
        rows = _make_wr_rows([500.0, 400.0, 350.0, 320.0, 300.0])
        history = _build_gap_history(rows, tas_time_s=250.0, first_wr_s=500.0)
        assert len(history) == 5

    def test_gap_decreases_as_wr_improves(self):
        rows = _make_wr_rows([500.0, 400.0, 350.0, 300.0])
        history = _build_gap_history(rows, tas_time_s=250.0, first_wr_s=500.0)
        gaps = [s.gap_to_tas_s for s in history]
        assert gaps == sorted(gaps, reverse=True)

    def test_gap_clamped_to_zero_when_wr_beats_tas(self):
        rows = _make_wr_rows([500.0, 400.0, 300.0, 240.0])
        history = _build_gap_history(rows, tas_time_s=250.0, first_wr_s=500.0)
        assert history[-1].gap_to_tas_s == 0.0

    def test_returns_tas_gap_snapshot_objects(self):
        rows = _make_wr_rows([500.0, 400.0])
        history = _build_gap_history(rows, tas_time_s=300.0, first_wr_s=500.0)
        assert all(isinstance(s, TasGapSnapshot) for s in history)

    def test_to_dict_has_required_keys(self):
        rows = _make_wr_rows([500.0, 400.0])
        history = _build_gap_history(rows, tas_time_s=300.0, first_wr_s=500.0)
        d = history[0].to_dict()
        for key in ("wr_number", "date", "wr_time_s", "gap_to_tas_s", "gap_pct"):
            assert key in d

    def test_gap_pct_non_negative(self):
        rows = _make_wr_rows([500.0, 450.0, 400.0, 350.0])
        history = _build_gap_history(rows, tas_time_s=300.0, first_wr_s=500.0)
        assert all(s.gap_pct >= 0 for s in history)

    def test_first_entry_has_largest_gap(self):
        rows = _make_wr_rows([500.0, 450.0, 400.0, 350.0])
        history = _build_gap_history(rows, tas_time_s=300.0, first_wr_s=500.0)
        assert history[0].gap_to_tas_s == max(s.gap_to_tas_s for s in history)

    def test_wr_number_sequential(self):
        rows = _make_wr_rows([500.0, 400.0, 350.0])
        history = _build_gap_history(rows, tas_time_s=300.0, first_wr_s=500.0)
        assert [s.wr_number for s in history] == [1, 2, 3]


# ---------- _gap_velocity ----------

class TestGapVelocity:
    def test_positive_when_gap_shrinking(self):
        # WR improving → gap to TAS shrinking → positive velocity
        rows = _make_wr_rows([500.0, 450.0, 420.0, 400.0, 380.0, 360.0],
                              dates=["2010-01-01", "2011-01-01", "2012-01-01",
                                     "2013-01-01", "2014-01-01", "2015-01-01"])
        v = _gap_velocity(rows, tas_time_s=300.0)
        assert v is not None
        assert v > 0

    def test_returns_none_for_single_row(self):
        rows = _make_wr_rows([500.0])
        assert _gap_velocity(rows, tas_time_s=300.0) is None

    def test_zero_when_gap_not_closing(self):
        # WR stopped improving → gap constant → velocity ≈ 0.
        # Need at least 7 rows so that recent_n=5 stays entirely in the stagnant zone
        # (all 5 recent WRs at 350 s; the early 500→350 drop is outside the window).
        rows = _make_wr_rows([500.0, 350.0, 350.0, 350.0, 350.0, 350.0, 350.0],
                              dates=["2010-01-01", "2011-01-01", "2012-01-01",
                                     "2013-01-01", "2014-01-01", "2015-01-01", "2016-01-01"])
        v = _gap_velocity(rows, tas_time_s=300.0)
        assert v is not None
        assert abs(v) < 0.1  # all 5 recent WRs identical → velocity ≈ 0

    def test_uses_recent_wrs_not_full_history(self):
        # Early WRs improved rapidly, but last 5 have been stagnant
        # The velocity should reflect the stagnant period, not the whole history
        early = [500.0, 400.0, 350.0]  # fast improvement
        recent = [348.0, 347.0, 346.5, 346.2, 346.0, 345.9]  # tiny improvements
        times = early + recent
        dates = [f"200{i}-01-01" for i in range(len(times))]
        rows = _make_wr_rows(times, dates)
        v = _gap_velocity(rows, tas_time_s=300.0)
        # Should be small (recent stagnation) not large (historical burst)
        assert v is not None
        assert v < 10.0  # less than 10 s/year


# ---------- _analyse_game ----------

class TestAnalyseGame:
    _TIMES  = [500.0, 450.0, 420.0, 400.0, 380.0]
    _DATES  = ["2010-01-01", "2012-01-01", "2014-01-01", "2016-01-01", "2018-01-01"]
    _TAS    = 300.0
    _INFO   = {"tas_time_s": _TAS, "source": "TestTAS", "confidence": "high"}

    def test_returns_none_when_tas_time_is_none(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("TestGame", rows, {"tas_time_s": None}, {})
        assert result is None

    def test_returns_none_for_single_row(self):
        rows = _make_wr_rows([500.0])
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert result is None

    def test_returns_tas_comparison_result(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert isinstance(result, TasComparisonResult)

    def test_current_gap_is_positive(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert result.current_gap_s >= 0

    def test_gap_equals_wr_minus_tas(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        expected_gap = max(0.0, float(self._TIMES[-1]) - self._TAS)
        assert abs(result.current_gap_s - expected_gap) < 0.01

    def test_pct_closed_in_0_100(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        if result.pct_closed is not None:
            assert 0.0 <= result.pct_closed <= 100.0

    def test_gap_history_length_matches_wr_count(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert result is not None
        assert len(result.gap_history) == len(self._TIMES)

    def test_game_field_matches_input(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("Celeste", rows, self._INFO, {})
        assert result.game == "Celeste"

    def test_tas_time_stored_correctly(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert abs(result.tas_time_s - self._TAS) < 0.01

    def test_model_vs_tas_delta_computed_when_floor_available(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        model_floors = {"TestGame": 310.0}
        result = _analyse_game("TestGame", rows, self._INFO, model_floors)
        assert result is not None
        assert result.model_vs_tas_delta_s is not None
        assert abs(result.model_vs_tas_delta_s - (310.0 - self._TAS)) < 0.01

    def test_model_vs_tas_none_when_no_floor(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert result.model_vs_tas_delta_s is None

    def test_to_dict_has_required_keys(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert result is not None
        d = result.to_dict()
        for key in ("game", "tas_time_s", "current_wr_time_s", "current_gap_s",
                    "pct_closed", "gap_history", "model_floor_s", "model_vs_tas_delta_s"):
            assert key in d

    def test_returns_none_when_tas_above_first_wr(self):
        # TAS time >= first WR makes no physical sense
        rows = _make_wr_rows([300.0, 280.0, 260.0], self._DATES[:3])
        info = {"tas_time_s": 400.0, "source": "TestTAS"}
        result = _analyse_game("TestGame", rows, info, {})
        assert result is None

    def test_gap_zero_when_wr_matches_tas(self):
        rows = _make_wr_rows([500.0, 400.0, 300.0], self._DATES[:3])
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert result is not None
        assert result.current_gap_s == 0.0


# ---------- _cross_game_summary ----------

class TestCrossGameSummary:
    def _make_result(self, game: str, tas: float, current: float,
                     first: float = 500.0, model_floor: float | None = None) -> TasComparisonResult:
        gap = max(0.0, current - tas)
        gap_pct = round(gap / first * 100, 3)
        pct_closed = round((first - current) / (first - tas) * 100, 2) if first != tas else None
        return TasComparisonResult(
            game=game, tas_time_s=tas, tas_source="Test",
            first_wr_time_s=first, current_wr_time_s=current,
            current_gap_s=gap, current_gap_pct=gap_pct, pct_closed=pct_closed,
            gap_velocity_s_per_year=2.0, est_years_to_match_tas=None,
            gap_history=[], model_floor_s=model_floor,
            model_vs_tas_delta_s=round(model_floor - tas, 3) if model_floor is not None else None,
        )

    def test_empty_results_returns_empty_dict(self):
        assert _cross_game_summary([]) == {}

    def test_n_games_correct(self):
        results = [self._make_result("G1", 300.0, 380.0),
                   self._make_result("G2", 100.0, 120.0)]
        s = _cross_game_summary(results)
        assert s["n_games_with_tas"] == 2

    def test_mean_gap_pct_non_negative(self):
        results = [self._make_result("G1", 300.0, 380.0),
                   self._make_result("G2", 100.0, 120.0)]
        s = _cross_game_summary(results)
        assert s["mean_gap_pct"] >= 0

    def test_fully_matched_tas_correct(self):
        results = [
            self._make_result("G1", 300.0, 300.5),   # gap 0.5 s < 1.0 → matched
            self._make_result("G2", 100.0, 150.0),   # gap 50 s → not matched
        ]
        s = _cross_game_summary(results)
        assert s["fully_matched_tas"] == 1

    def test_model_validation_included_when_deltas_present(self):
        results = [
            self._make_result("G1", 300.0, 380.0, model_floor=310.0),
            self._make_result("G2", 100.0, 120.0, model_floor=105.0),
        ]
        s = _cross_game_summary(results)
        assert "model_validation" in s
        assert s["model_validation"]["n_games_with_both_model_and_tas"] == 2

    def test_model_validation_absent_when_no_deltas(self):
        results = [self._make_result("G1", 300.0, 380.0)]  # no model_floor
        s = _cross_game_summary(results)
        assert "model_validation" not in s

    def test_mean_pct_closed_in_0_100(self):
        results = [self._make_result("G1", 300.0, 380.0),
                   self._make_result("G2", 100.0, 120.0)]
        s = _cross_game_summary(results)
        if s["mean_pct_closed"] is not None:
            assert 0.0 <= s["mean_pct_closed"] <= 100.0


# ---------- TasGapSnapshot DTO ----------

class TestTasGapSnapshot:
    def test_to_dict_complete(self):
        s = TasGapSnapshot(wr_number=3, date="2020-06-01", wr_time_s=380.0,
                           gap_to_tas_s=80.0, gap_pct=16.0)
        d = s.to_dict()
        assert d["wr_number"]    == 3
        assert d["date"]         == "2020-06-01"
        assert d["wr_time_s"]    == 380.0
        assert d["gap_to_tas_s"] == 80.0
        assert d["gap_pct"]      == 16.0


# ---------- TasComparisonResult DTO ----------

class TestTasComparisonResult:
    def _make(self) -> TasComparisonResult:
        snap = TasGapSnapshot(1, "2020-01-01", 400.0, 100.0, 25.0)
        return TasComparisonResult(
            game="TestGame", tas_time_s=300.0, tas_source="TASVideos",
            first_wr_time_s=500.0, current_wr_time_s=400.0,
            current_gap_s=100.0, current_gap_pct=20.0, pct_closed=50.0,
            gap_velocity_s_per_year=5.0, est_years_to_match_tas=20.0,
            gap_history=[snap], model_floor_s=310.0, model_vs_tas_delta_s=10.0,
        )

    def test_to_dict_game_field(self):
        assert self._make().to_dict()["game"] == "TestGame"

    def test_to_dict_gap_history_is_list_of_dicts(self):
        d = self._make().to_dict()
        assert isinstance(d["gap_history"], list)
        assert isinstance(d["gap_history"][0], dict)

    def test_to_dict_all_top_level_keys(self):
        d = self._make().to_dict()
        for k in ("game", "tas_time_s", "tas_source", "first_wr_time_s",
                  "current_wr_time_s", "current_gap_s", "current_gap_pct",
                  "pct_closed", "gap_velocity_s_per_year", "est_years_to_match_tas",
                  "gap_history", "model_floor_s", "model_vs_tas_delta_s"):
            assert k in d, f"missing key: {k}"


# ---------- integration: _load_tas_reference with temp file ----------

class TestLoadTasReference:
    def test_loads_json_file(self, tmp_path):
        ref = {"games": {"TestGame": {"tas_time_s": 300.0}}}
        p = tmp_path / "reference" / "tas_known.json"
        p.parent.mkdir()
        p.write_text(json.dumps(ref), encoding="utf-8")

        import f3b_tas_analysis as m
        original = m.REFERENCE_DIR
        m.REFERENCE_DIR = tmp_path / "reference"
        try:
            result = m._load_tas_reference()
            assert result["games"]["TestGame"]["tas_time_s"] == 300.0
        finally:
            m.REFERENCE_DIR = original

    def test_raises_when_missing(self, tmp_path):
        import f3b_tas_analysis as m
        original = m.REFERENCE_DIR
        m.REFERENCE_DIR = tmp_path
        try:
            with pytest.raises(FileNotFoundError):
                m._load_tas_reference()
        finally:
            m.REFERENCE_DIR = original
