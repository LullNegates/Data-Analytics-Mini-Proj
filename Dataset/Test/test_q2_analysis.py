"""Tests for analysis/q2_analysis.py helper functions."""

import numpy as np
import pytest

import q2_analysis
from q2_analysis import _detect_structural_break, _analyse_game


def _make_rows(times_s: list[float], days: list[float] | None = None,
               game: str = "TestGame", genre: str = "Platformer") -> list[dict]:
    """Build minimal q2_saturation rows from WR times and optional days offsets."""
    if days is None:
        days = [float(i * 30) for i in range(len(times_s))]
    imps = [0.0] + [times_s[i - 1] - times_s[i] for i in range(1, len(times_s))]
    total_red = times_s[0] - times_s[-1]
    cumulative = 0.0
    rows = []
    for i, (t, d, imp) in enumerate(zip(times_s, days, imps)):
        cumulative += max(0.0, imp)
        pct = round(cumulative / total_red * 100, 2) if total_red > 0 else 0.0
        rows.append({
            "game":                  game,
            "genre":                 genre,
            "wr_number":             str(i + 1),
            "date":                  f"2010-01-{(i % 28) + 1:02d}",
            "days_since_first":      str(d),
            "time_seconds":          str(t),
            "improvement_s":         str(max(0.0, imp)),
            "pct_of_total_reduction": str(pct),
        })
    return rows


# ---------- _detect_structural_break ----------

class TestDetectStructuralBreak:
    """_detect_structural_break returns a StructuralBreakResult DTO or None."""

    def _call(self, rows):
        x = np.array([float(r["days_since_first"]) for r in rows])
        y = np.array([float(r["time_seconds"]) for r in rows])
        return _detect_structural_break(x, y, rows)

    def test_returns_none_for_too_few_points(self):
        rows = _make_rows([200.0, 190.0, 180.0, 170.0, 160.0])
        assert self._call(rows) is None

    def test_detects_significant_break(self):
        left_times  = [200.0 - i * 1.0 for i in range(8)]
        right_times = [left_times[-1] - i * 15.0 for i in range(8)]
        rows   = _make_rows(left_times + right_times,
                            [float(i * 30) for i in range(16)])
        result = self._call(rows)
        assert result is not None
        assert result.significant_at_005 is True

    def test_no_significant_break_on_noisy_linear_trend(self):
        import random
        rng   = random.Random(99)
        times = [200.0 - i * 5.0 + rng.gauss(0, 0.2) for i in range(16)]
        days  = [float(i * 30) for i in range(16)]
        rows  = _make_rows(times, days)
        result = self._call(rows)
        if result is not None:
            assert result.f_statistic < 15.0

    def test_result_has_required_attributes(self):
        left_times  = [200.0 - i * 0.5 for i in range(8)]
        right_times = [left_times[-1] - i * 20.0 for i in range(8)]
        rows   = _make_rows(left_times + right_times)
        result = self._call(rows)
        if result is not None:
            assert hasattr(result, "split_wr_number")
            assert hasattr(result, "split_date")
            assert hasattr(result, "f_statistic")
            assert hasattr(result, "significant_at_005")

    def test_to_dict_uses_dot_05_key(self):
        left_times  = [200.0 - i * 0.5 for i in range(8)]
        right_times = [left_times[-1] - i * 20.0 for i in range(8)]
        rows   = _make_rows(left_times + right_times)
        result = self._call(rows)
        if result is not None:
            d = result.to_dict()
            assert "significant_at_0.05" in d

    def test_f_statistic_is_non_negative(self):
        left_times  = [200.0 - i * 0.5 for i in range(8)]
        right_times = [left_times[-1] - i * 20.0 for i in range(8)]
        rows   = _make_rows(left_times + right_times)
        result = self._call(rows)
        if result is not None:
            assert result.f_statistic >= 0


# ---------- _analyse_game ----------

class TestAnalyseGame:
    """_analyse_game returns a GameQ2Result DTO."""

    def test_returns_dto_with_required_attributes(self):
        times  = [200.0 - i * 3.0 for i in range(12)]
        rows   = _make_rows(times)
        result = _analyse_game("TestGame", rows)
        assert hasattr(result, "game")
        assert hasattr(result, "best_model")
        assert hasattr(result, "model_comparison")
        assert hasattr(result, "improvement_acceleration")
        assert hasattr(result, "structural_break")

    def test_game_and_genre_match_input(self):
        rows   = _make_rows([200.0 - i * 3.0 for i in range(12)], game="MyGame", genre="FPS")
        result = _analyse_game("MyGame", rows)
        assert result.game  == "MyGame"
        assert result.genre == "FPS"

    def test_best_model_is_dict_or_none(self):
        rows   = _make_rows([200.0 - i * 3.0 for i in range(12)])
        result = _analyse_game("TestGame", rows)
        if result.best_model is not None:
            assert "model" in result.best_model
            assert "r2"    in result.best_model

    def test_improvement_acceleration_sign_for_decelerating(self):
        imps  = [50.0, 30.0, 20.0, 10.0, 8.0, 5.0, 3.0, 1.0, 0.5, 0.2, 0.1, 0.05]
        times = [300.0]
        for imp in imps:
            times.append(times[-1] - imp)
        days   = [float(i * 60) for i in range(len(times))]
        rows   = _make_rows(times, days)
        result = _analyse_game("TestGame", rows)
        if result.improvement_acceleration is not None:
            assert result.improvement_acceleration.interpretation == "decelerating"

    def test_to_dict_has_required_keys(self):
        rows   = _make_rows([200.0 - i * 3.0 for i in range(12)])
        result = _analyse_game("TestGame", rows)
        d = result.to_dict()
        for key in ("game", "genre", "n_wrs", "span_days", "best_model",
                    "model_comparison", "improvement_acceleration", "structural_break"):
            assert key in d

    def test_n_wrs_equals_row_count(self):
        times  = [200.0 - i * 3.0 for i in range(10)]
        rows   = _make_rows(times)
        result = _analyse_game("TestGame", rows)
        assert result.n_wrs == len(rows)

    def test_span_days_non_negative(self):
        times  = [200.0 - i * 3.0 for i in range(10)]
        days   = [float(i * 45) for i in range(10)]
        rows   = _make_rows(times, days)
        result = _analyse_game("TestGame", rows)
        assert result.span_days >= 0

    def test_improvement_acceleration_is_dto_or_none(self):
        from shared.DTOs.q2_dtos import ImprovementAccelerationResult
        rows   = _make_rows([200.0 - i * 3.0 for i in range(12)])
        result = _analyse_game("TestGame", rows)
        assert result.improvement_acceleration is None or \
               isinstance(result.improvement_acceleration, ImprovementAccelerationResult)

    def test_structural_break_is_dto_or_none(self):
        from shared.DTOs.q2_dtos import StructuralBreakResult
        rows   = _make_rows([200.0 - i * 3.0 for i in range(12)])
        result = _analyse_game("TestGame", rows)
        assert result.structural_break is None or \
               isinstance(result.structural_break, StructuralBreakResult)


# ---------- run() smoke — requires no real CSV ----------

class TestLoadCsvMissing:
    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            q2_analysis._load_csv("__no_such_file__.csv")
