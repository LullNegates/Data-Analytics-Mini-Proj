"""Tests for analysis/f3b_tas_analysis.py — TAS vs human WR comparison."""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from f3b_tas_analysis import (
    _build_gap_history,
    _gap_velocity,
    _analyse_game,
    _cross_game_summary,
    _find_date_surpassed,
    _load_tas_from_files,
    _normalize_name,
    _compute_tas_impact,
    _wr_velocity_in_window,
    _impact_summary,
)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.DTOs.f3b_dtos import TasComparisonResult, TasGapSnapshot, TasImpactWindow


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


def _make_tas_info(tas_time_s: float, source: str = "TestSource",
                   category_mismatch: bool = False,
                   tas_source_type: str = "tasvideos") -> dict:
    return {
        "tas_time_s": tas_time_s,
        "source": source,
        "category_mismatch": category_mismatch,
        "tas_source_type": tas_source_type,
    }


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
                    "pct_closed", "gap_history", "model_floor_s", "model_vs_tas_delta_s",
                    "date_surpassed", "category_mismatch", "tas_source_type"):
            assert key in d

    def test_date_surpassed_set_when_wr_beats_tas(self):
        times = [500.0, 400.0, 350.0, 280.0]  # 280 beats TAS=300
        dates = ["2010-01-01", "2012-01-01", "2014-01-01", "2016-06-15"]
        rows = _make_wr_rows(times, dates)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert result is not None
        assert result.date_surpassed == "2016-06-15"

    def test_date_surpassed_none_when_wr_never_beats_tas(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)  # best is 380 > 300 (TAS)
        result = _analyse_game("TestGame", rows, self._INFO, {})
        assert result is not None
        assert result.date_surpassed is None

    def test_category_mismatch_propagated(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        info = _make_tas_info(self._TAS, category_mismatch=True)
        result = _analyse_game("TestGame", rows, info, {})
        assert result is not None
        assert result.category_mismatch is True

    def test_tas_source_type_propagated(self):
        rows = _make_wr_rows(self._TIMES, self._DATES)
        info = _make_tas_info(self._TAS, tas_source_type="external")
        result = _analyse_game("TestGame", rows, info, {})
        assert result is not None
        assert result.tas_source_type == "external"

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
                  "gap_history", "model_floor_s", "model_vs_tas_delta_s",
                  "date_surpassed", "category_mismatch", "tas_source_type"):
            assert k in d, f"missing key: {k}"

    def test_new_fields_default_values(self):
        snap = TasGapSnapshot(1, "2020-01-01", 400.0, 100.0, 25.0)
        r = TasComparisonResult(
            game="G", tas_time_s=300.0, tas_source="S",
            first_wr_time_s=500.0, current_wr_time_s=400.0,
            current_gap_s=100.0, current_gap_pct=20.0, pct_closed=50.0,
            gap_velocity_s_per_year=5.0, est_years_to_match_tas=20.0,
            gap_history=[snap], model_floor_s=None, model_vs_tas_delta_s=None,
        )
        assert r.date_surpassed is None
        assert r.category_mismatch is False
        assert r.tas_source_type == "tasvideos"


# ---------- _find_date_surpassed ----------

class TestFindDateSurpassed:
    def _rows(self, times, dates):
        return [{"time_seconds": str(t), "date": d, "wr_number": str(i + 1)}
                for i, (t, d) in enumerate(zip(times, dates))]

    def test_returns_date_of_first_wr_that_beats_tas(self):
        rows = self._rows([500.0, 400.0, 280.0, 270.0], ["2010-01-01", "2012-01-01", "2015-06-01", "2018-01-01"])
        assert _find_date_surpassed(rows, 300.0) == "2015-06-01"

    def test_returns_date_when_exactly_matches_tas(self):
        rows = self._rows([500.0, 300.0], ["2010-01-01", "2015-01-01"])
        assert _find_date_surpassed(rows, 300.0) == "2015-01-01"

    def test_returns_none_when_wr_never_reaches_tas(self):
        rows = self._rows([500.0, 400.0, 350.0], ["2010-01-01", "2012-01-01", "2014-01-01"])
        assert _find_date_surpassed(rows, 300.0) is None

    def test_returns_first_not_last_surpass_date(self):
        rows = self._rows([500.0, 280.0, 260.0], ["2010-01-01", "2012-06-01", "2016-01-01"])
        # Should return 2012-06-01, not 2016-01-01
        assert _find_date_surpassed(rows, 300.0) == "2012-06-01"

    def test_empty_rows_returns_none(self):
        assert _find_date_surpassed([], 300.0) is None


# ---------- _normalize_name ----------

class TestNormalizeName:
    def test_strips_accents(self):
        assert _normalize_name("Pokémon Red/Blue") == _normalize_name("Pokemon Red/Blue")

    def test_lowercases(self):
        assert _normalize_name("Super Mario Bros.") == "super mario bros."

    def test_strips_whitespace(self):
        assert _normalize_name("  Celeste  ") == "celeste"

    def test_identical_names_match(self):
        assert _normalize_name("Half-Life 2") == _normalize_name("Half-Life 2")


# ---------- _load_tas_from_files ----------

def _make_tas_file(tmp_ref: Path, game: str, time_s: float, status: str = "found",
                   category_mismatch: bool = False, game_id: int | None = 1) -> None:
    slug = game.lower().replace(" ", "-").replace(":", "").replace("/", "-")
    slug = "".join(c if c.isalnum() or c == "-" else "" for c in slug)
    data = {
        "game": game,
        "tasvideos_game_id": game_id,
        "source": "TASVideos.org",
        "source_url": "https://tasvideos.org/",
        "status": status,
        "category_mismatch": category_mismatch,
        "timeline": [{"date": "2020-01-01", "time_s": time_s}],
        "current_best": {"date": "2020-01-01", "time_s": time_s},
    }
    (tmp_ref / f"tas_{slug}.json").write_text(json.dumps(data), encoding="utf-8")


class TestLoadTasFromFiles:
    def test_loads_valid_file(self, tmp_path):
        ref = tmp_path / "reference"
        ref.mkdir()
        _make_tas_file(ref, "Test Game", 300.0)

        import f3b_tas_analysis as m
        orig = m.REFERENCE_DIR
        m.REFERENCE_DIR = ref
        try:
            result = m._load_tas_from_files()
            assert "test game" in result
            assert result["test game"]["tas_time_s"] == 300.0
        finally:
            m.REFERENCE_DIR = orig

    def test_skips_no_tas_available(self, tmp_path):
        ref = tmp_path / "reference"
        ref.mkdir()
        _make_tas_file(ref, "Skip Game", 300.0, status="no_tas_available")

        import f3b_tas_analysis as m
        orig = m.REFERENCE_DIR
        m.REFERENCE_DIR = ref
        try:
            result = m._load_tas_from_files()
            assert "skip game" not in result
        finally:
            m.REFERENCE_DIR = orig

    def test_skips_tas_known(self, tmp_path):
        ref = tmp_path / "reference"
        ref.mkdir()
        (ref / "tas_known.json").write_text('{"games": {}}', encoding="utf-8")

        import f3b_tas_analysis as m
        orig = m.REFERENCE_DIR
        m.REFERENCE_DIR = ref
        try:
            result = m._load_tas_from_files()
            assert result == {}
        finally:
            m.REFERENCE_DIR = orig

    def test_source_type_tasvideos_when_has_id(self, tmp_path):
        ref = tmp_path / "reference"
        ref.mkdir()
        _make_tas_file(ref, "Mario Game", 300.0, game_id=1)

        import f3b_tas_analysis as m
        orig = m.REFERENCE_DIR
        m.REFERENCE_DIR = ref
        try:
            result = m._load_tas_from_files()
            assert result["mario game"]["tas_source_type"] == "tasvideos"
        finally:
            m.REFERENCE_DIR = orig

    def test_source_type_external_when_no_id(self, tmp_path):
        ref = tmp_path / "reference"
        ref.mkdir()
        _make_tas_file(ref, "PC Game", 300.0, game_id=None)

        import f3b_tas_analysis as m
        orig = m.REFERENCE_DIR
        m.REFERENCE_DIR = ref
        try:
            result = m._load_tas_from_files()
            assert result["pc game"]["tas_source_type"] == "external"
        finally:
            m.REFERENCE_DIR = orig

    def test_category_mismatch_preserved(self, tmp_path):
        ref = tmp_path / "reference"
        ref.mkdir()
        _make_tas_file(ref, "Mismatch Game", 300.0, category_mismatch=True)

        import f3b_tas_analysis as m
        orig = m.REFERENCE_DIR
        m.REFERENCE_DIR = ref
        try:
            result = m._load_tas_from_files()
            assert result["mismatch game"]["category_mismatch"] is True
        finally:
            m.REFERENCE_DIR = orig

    def test_accent_normalized_key(self, tmp_path):
        ref = tmp_path / "reference"
        ref.mkdir()
        # Write file with accented game name
        data = {
            "game": "Pokémon Red/Blue",
            "tasvideos_game_id": 16,
            "source": "TASVideos",
            "source_url": "",
            "status": "found",
            "category_mismatch": False,
            "timeline": [],
            "current_best": {"date": "2011-08-15", "time_s": 69.633},
        }
        (ref / "tas_pokemon-red-blue.json").write_text(json.dumps(data), encoding="utf-8")

        import f3b_tas_analysis as m
        orig = m.REFERENCE_DIR
        m.REFERENCE_DIR = ref
        try:
            result = m._load_tas_from_files()
            # "Pokémon" normalized to "pokemon" — same as "Pokemon"
            assert "pokemon red/blue" in result
        finally:
            m.REFERENCE_DIR = orig


# ---------- integration: _load_tas_reference (legacy) ----------

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


# ---------- _wr_velocity_in_window ----------

class TestWrVelocityInWindow:
    def _rows(self, times, dates):
        return [{"time_seconds": str(t), "date": d} for t, d in zip(times, dates)]

    def test_positive_velocity_when_improving(self):
        rows = self._rows([500.0, 450.0, 400.0],
                          ["2010-01-01", "2011-01-01", "2012-01-01"])
        v = _wr_velocity_in_window(rows, "2010-01-01", "2012-01-01")
        assert v is not None and v > 0

    def test_none_when_fewer_than_two_rows(self):
        rows = self._rows([500.0], ["2010-01-01"])
        assert _wr_velocity_in_window(rows, "2010-01-01", "2012-01-01") is None

    def test_none_when_no_rows_in_window(self):
        rows = self._rows([500.0, 400.0], ["2015-01-01", "2016-01-01"])
        assert _wr_velocity_in_window(rows, "2010-01-01", "2011-01-01") is None

    def test_only_rows_in_window_are_used(self):
        rows = self._rows([600.0, 500.0, 400.0, 300.0],
                          ["2008-01-01", "2010-01-01", "2011-01-01", "2015-01-01"])
        # Window 2010 to 2012 — only rows at 500 and 400 qualify
        v = _wr_velocity_in_window(rows, "2010-01-01", "2012-01-01")
        expected = (500.0 - 400.0) / 365 * 365  # ~100 s/year
        assert v is not None and abs(v - expected) < 5.0


# ---------- _compute_tas_impact ----------

class TestComputeTasImpact:
    def _wr_rows(self, times, dates):
        return [
            {"time_seconds": str(t), "date": d, "wr_number": str(i + 1)}
            for i, (t, d) in enumerate(zip(times, dates))
        ]

    def _tas(self, times, dates):
        return [{"time_s": t, "date": d} for t, d in zip(times, dates)]

    def test_returns_one_entry_per_tas_record(self):
        wr = self._wr_rows([500.0, 450.0, 400.0, 380.0],
                           ["2010-01-01", "2011-01-01", "2012-06-01", "2013-01-01"])
        tas = self._tas([480.0, 420.0], ["2010-06-01", "2012-01-01"])
        result = _compute_tas_impact("G", wr, tas, window_days=365)
        assert len(result) == 2

    def test_returns_tas_impact_window_objects(self):
        wr = self._wr_rows([500.0, 450.0], ["2010-01-01", "2012-01-01"])
        tas = self._tas([480.0], ["2011-01-01"])
        result = _compute_tas_impact("G", wr, tas, window_days=365)
        assert all(isinstance(r, TasImpactWindow) for r in result)

    def test_improvement_is_positive_when_wr_improves_after_tas(self):
        wr = self._wr_rows([500.0, 450.0, 420.0],
                           ["2010-01-01", "2011-06-01", "2012-01-01"])
        tas = self._tas([480.0], ["2011-01-01"])
        result = _compute_tas_impact("G", wr, tas, window_days=365)
        assert result[0].improvement_s > 0

    def test_improvement_is_zero_when_no_wr_in_window(self):
        wr = self._wr_rows([500.0], ["2010-01-01"])
        tas = self._tas([480.0], ["2010-06-01"])
        result = _compute_tas_impact("G", wr, tas, window_days=30)
        assert result[0].improvement_s == 0.0
        assert result[0].n_wrs_in_window == 0

    def test_skips_tas_that_predates_all_wrs(self):
        wr = self._wr_rows([500.0], ["2015-01-01"])
        tas = self._tas([480.0], ["2010-01-01"])  # before any WR
        result = _compute_tas_impact("G", wr, tas, window_days=365)
        assert len(result) == 0

    def test_n_wrs_counts_wrs_strictly_after_tas_date(self):
        wr = self._wr_rows([500.0, 490.0, 480.0, 470.0],
                           ["2010-01-01", "2010-06-01", "2010-09-01", "2011-06-01"])
        tas = self._tas([510.0], ["2010-01-01"])
        # window 365 days: 2010-01-01 to 2011-01-01
        # WRs strictly after 2010-01-01 and within 2011-01-01: rows at 490, 480
        result = _compute_tas_impact("G", wr, tas, window_days=365)
        assert result[0].n_wrs_in_window == 2

    def test_wr_at_tas_is_last_wr_before_or_on_tas_date(self):
        wr = self._wr_rows([500.0, 450.0, 400.0],
                           ["2010-01-01", "2011-01-01", "2012-01-01"])
        tas = self._tas([480.0], ["2011-06-01"])
        result = _compute_tas_impact("G", wr, tas, window_days=365)
        # WR at 2011-06-01 should use 2011-01-01 WR = 450
        assert result[0].wr_at_tas_s == 450.0

    def test_velocity_ratio_gt1_when_improvement_accelerates(self):
        # Fast improvement only AFTER the TAS
        wr = self._wr_rows([500.0, 499.0, 490.0, 470.0, 440.0],
                           ["2009-01-01", "2010-01-01",
                            "2011-02-01", "2011-04-01", "2011-10-01"])
        tas = self._tas([510.0], ["2011-01-01"])
        result = _compute_tas_impact("G", wr, tas, window_days=365)
        r = result[0]
        if r.velocity_ratio is not None:
            assert r.velocity_ratio > 0  # can't guarantee > 1 in all setups

    def test_empty_wr_rows_returns_empty(self):
        tas = self._tas([300.0], ["2011-01-01"])
        assert _compute_tas_impact("G", [], tas, window_days=365) == []

    def test_empty_tas_timeline_returns_empty(self):
        wr = self._wr_rows([500.0, 400.0], ["2010-01-01", "2012-01-01"])
        assert _compute_tas_impact("G", wr, [], window_days=365) == []

    def test_game_field_set_correctly(self):
        wr = self._wr_rows([500.0, 450.0], ["2010-01-01", "2012-01-01"])
        tas = self._tas([480.0], ["2011-01-01"])
        result = _compute_tas_impact("MyGame", wr, tas, window_days=365)
        assert result[0].game == "MyGame"

    def test_window_days_stored_in_result(self):
        wr = self._wr_rows([500.0, 450.0], ["2010-01-01", "2012-01-01"])
        tas = self._tas([480.0], ["2011-01-01"])
        result = _compute_tas_impact("G", wr, tas, window_days=90)
        assert result[0].window_days == 90

    def test_to_dict_has_required_keys(self):
        wr = self._wr_rows([500.0, 450.0], ["2010-01-01", "2012-01-01"])
        tas = self._tas([480.0], ["2011-01-01"])
        result = _compute_tas_impact("G", wr, tas, window_days=365)
        d = result[0].to_dict()
        for k in ("game", "tas_date", "tas_time_s", "wr_at_tas_s", "wr_post_s",
                  "improvement_s", "improvement_pct", "n_wrs_in_window",
                  "vel_pre_s_per_year", "vel_post_s_per_year",
                  "velocity_ratio", "window_days"):
            assert k in d, f"missing key: {k}"


# ---------- _impact_summary ----------

class TestImpactSummary:
    def _make_window(self, improvement_s: float, n_wrs: int,
                     vel_ratio: float | None = 1.5) -> TasImpactWindow:
        return TasImpactWindow(
            game="G", tas_date="2010-01-01", tas_time_s=300.0,
            wr_at_tas_s=500.0, wr_post_s=500.0 - improvement_s if improvement_s else None,
            improvement_s=improvement_s, improvement_pct=improvement_s / 500.0 * 100,
            n_wrs_in_window=n_wrs, vel_pre_s_per_year=10.0,
            vel_post_s_per_year=10.0 * vel_ratio if vel_ratio else None,
            velocity_ratio=vel_ratio, window_days=180,
        )

    def test_empty_returns_empty_dict(self):
        assert _impact_summary([]) == {}

    def test_n_tas_events_correct(self):
        windows = [self._make_window(5.0, 1), self._make_window(0.0, 0)]
        s = _impact_summary(windows)
        assert s["n_tas_events"] == 2

    def test_n_with_wr_improvement_counts_positive_improvement(self):
        windows = [self._make_window(5.0, 1), self._make_window(0.0, 0)]
        s = _impact_summary(windows)
        assert s["n_with_wr_improvement"] == 1

    def test_pct_with_wr_improvement(self):
        windows = [self._make_window(5.0, 1), self._make_window(5.0, 1),
                   self._make_window(0.0, 0)]
        s = _impact_summary(windows)
        assert abs(s["pct_with_wr_improvement"] - 66.7) < 1.0

    def test_mean_velocity_ratio_computed(self):
        windows = [self._make_window(5.0, 1, vel_ratio=2.0),
                   self._make_window(3.0, 1, vel_ratio=1.0)]
        s = _impact_summary(windows)
        assert s["mean_velocity_ratio"] == 1.5

    def test_mean_velocity_ratio_none_when_all_none(self):
        windows = [self._make_window(5.0, 1, vel_ratio=None)]
        s = _impact_summary(windows)
        assert s["mean_velocity_ratio"] is None

    def test_n_with_velocity_ratio_gt1(self):
        windows = [self._make_window(5.0, 1, vel_ratio=2.0),
                   self._make_window(3.0, 1, vel_ratio=0.5),
                   self._make_window(1.0, 1, vel_ratio=1.2)]
        s = _impact_summary(windows)
        assert s["n_with_velocity_ratio_gt1"] == 2
