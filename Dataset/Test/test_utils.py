"""Tests for shared/utils.py -- normalize_columns and normalize_floats."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))

import pytest
from utils import normalize_columns, normalize_floats


# ============================================================
# normalize_columns
# ============================================================

class TestNormalizeColumnsBasic:
    """All values in a float-bearing column get the same dp."""

    def test_pure_float_column_padded_to_max_dp(self):
        rows = [{"x": 1.5}, {"x": 2.75}, {"x": 3.1}]
        out = normalize_columns(rows)
        dps = {len(r["x"].split(".")[1]) for r in out}
        assert dps == {2}, f"Expected all 2dp, got: {[r['x'] for r in out]}"

    def test_int_in_float_column_formatted_to_match(self):
        rows = [{"x": 1.5}, {"x": 2}, {"x": 3.125}]
        out = normalize_columns(rows)
        assert out[1]["x"] == "2.000", f"Int 2 should become '2.000', got {out[1]['x']!r}"
        assert out[0]["x"] == "1.500", f"1.5 should become '1.500', got {out[0]['x']!r}"

    def test_all_ints_column_left_unchanged(self):
        rows = [{"n": 1}, {"n": 2}, {"n": 3}]
        out = normalize_columns(rows)
        assert all(r["n"] == orig["n"] for r, orig in zip(out, rows))

    def test_string_column_passes_through(self):
        rows = [{"name": "Mario"}, {"name": "Link"}]
        out = normalize_columns(rows)
        assert out[0]["name"] == "Mario"

    def test_mixed_int_and_float_same_dp_across_all_rows(self):
        rows = [
            {"v": 99.4895},
            {"v": 89.755},
            {"v": 80},
            {"v": 7.5},
            {"v": 14},
            {"v": 100.0},
            {"v": 3.1},
            {"v": 0.123},
            {"v": 1234},
            {"v": 27.117},
        ]
        out = normalize_columns(rows)
        all_dp = {len(r["v"].split(".")[1]) for r in out}
        assert all_dp == {4}, f"All rows should have 4dp, got: {[r['v'] for r in out]}"

    def test_trailing_zeros_preserved_in_csv(self):
        rows = [{"t": 52.719}, {"t": 3137}, {"t": 1980}]
        out = normalize_columns(rows)
        assert out[1]["t"] == "3137.000"
        assert out[2]["t"] == "1980.000"

    def test_zero_float_formatted_correctly(self):
        rows = [{"v": 0.0}, {"v": 1.5}]
        out = normalize_columns(rows)
        assert out[0]["v"] == "0.0"

    def test_empty_rows_returns_empty(self):
        assert normalize_columns([]) == []

    def test_none_value_passes_through(self):
        rows = [{"v": None}, {"v": 1.5}]
        out = normalize_columns(rows)
        assert out[0]["v"] is None

    def test_bool_column_not_touched(self):
        rows = [{"flag": True}, {"flag": False}]
        out = normalize_columns(rows)
        assert out[0]["flag"] is True
        assert out[1]["flag"] is False


class TestNormalizeColumnsSampleData:
    """Regression tests based on actual speedrun data patterns."""

    def test_median_improvement_s_pattern(self):
        """Column mix: some values have 3dp, others are bare integers."""
        rows = [
            {"m": 4.110},
            {"m": 21},
            {"m": 1.635},
            {"m": 20},
            {"m": 7.140},
            {"m": 33.150},
            {"m": 5},
            {"m": 1.148},
            {"m": 22},
            {"m": 168},
        ]
        out = normalize_columns(rows)
        all_dp = {len(r["m"].split(".")[1]) for r in out}
        assert all_dp == {3}, f"All should be 3dp: {[r['m'] for r in out]}"
        assert out[1]["m"] == "21.000"
        assert out[3]["m"] == "20.000"
        assert out[6]["m"] == "5.000"

    def test_time_seconds_pattern(self):
        """Whole-second game times mixed with sub-second measurements."""
        rows = [
            {"t": 52.719},
            {"t": 3137},
            {"t": 192.500},
            {"t": 1980},
            {"t": 307.020},
            {"t": 8167},
            {"t": 31.890},
            {"t": 687},
            {"t": 2190.285},
            {"t": 294.415},
        ]
        out = normalize_columns(rows)
        all_dp = {len(r["t"].split(".")[1]) for r in out}
        assert all_dp == {3}, f"All should be 3dp: {[r['t'] for r in out]}"
        assert out[1]["t"] == "3137.000"
        assert out[3]["t"] == "1980.000"


# ============================================================
# normalize_floats
# ============================================================

class TestNormalizeFloatsListOfDicts:
    """list[dict] items are normalised per key to max dp."""

    def test_float_values_rounded_to_max_dp(self):
        data = [{"x": 1.5}, {"x": 2.75}, {"x": 3.1}]
        out = normalize_floats(data)
        assert all(abs(item["x"] - round(item["x"], 2)) < 1e-9 for item in out)

    def test_int_in_float_key_rounded_up(self):
        data = [{"v": 1.555}, {"v": 2}, {"v": 3.1}]
        out = normalize_floats(data)
        assert out[1]["v"] == 2.0
        assert abs(out[0]["v"] - round(1.555, 3)) < 1e-9

    def test_scientific_notation_preserved(self):
        data = [{"c": 9.138e-05}, {"c": 45.39519}]
        out = normalize_floats(data)
        assert out[0]["c"] == 9.138e-05, f"Scientific value must not be rounded away: {out[0]['c']}"

    def test_ten_values_uniform_dp(self):
        data = [
            {"p": 99.4895},
            {"p": 89.755},
            {"p": 80},
            {"p": 7.5},
            {"p": 14},
            {"p": 100.0},
            {"p": 3.1},
            {"p": 0.123},
            {"p": 1234},
            {"p": 27.117},
        ]
        out = normalize_floats(data)
        for item in out:
            v = item["p"]
            assert abs(v - round(v, 4)) < 1e-9, f"Value {v} not rounded to 4dp"


class TestNormalizeFloatsFlatDict:
    """Flat dict[str, float] normalised by max dp seen."""

    def test_flat_float_dict_normalised(self):
        gini = {"Platformer": 0.8748, "FPS": 0.753, "Sandbox": 0.9308, "RPG": 0.6547}
        out = normalize_floats(gini)
        for genre, v in out.items():
            assert abs(v - round(v, 4)) < 1e-9, f"{genre}: {v} not 4dp"
        assert abs(out["FPS"] - 0.7530) < 1e-9, "FPS gini should be 0.7530"

    def test_flat_int_float_mix(self):
        d = {"a": 1.555, "b": 2, "c": 3.1}
        out = normalize_floats(d)
        assert abs(out["b"] - 2.0) < 1e-9

    def test_ten_different_dp_values(self):
        d = {
            "k1": 0.8748,
            "k2": 0.753,
            "k3": 0.84,
            "k4": 0.9,
            "k5": 0.6547,
            "k6": 1.0,
            "k7": 0.8379,
            "k8": 0.7161,
            "k9": 0.9308,
            "k10": 0.8492,
        }
        out = normalize_floats(d)
        for k, v in out.items():
            assert abs(v - round(v, 4)) < 1e-9, f"{k}: {v} not rounded to 4dp"


class TestNormalizeFloatsDictOfDicts:
    """Homogeneous dict[str, dict] treated as virtual list."""

    def test_genre_stats_shape(self):
        genre_stats = {
            "FPS":       {"survival_at_365": 0.1063, "survival_at_730": 0.053},
            "Platformer":{"survival_at_365": 0.0605, "survival_at_730": 0.0093},
            "Sandbox":   {"survival_at_365": 0.0519, "survival_at_730": 0.026},
        }
        out = normalize_floats(genre_stats)
        for genre, s in out.items():
            assert abs(s["survival_at_730"] - round(s["survival_at_730"], 4)) < 1e-9, \
                f"{genre} survival_at_730 {s['survival_at_730']} not 4dp"

    def test_ten_genres_same_key_normalised(self):
        stats = {f"G{i}": {"score": v} for i, v in enumerate(
            [0.8748, 0.753, 0.84, 0.9, 0.6547, 1.0, 0.8379, 0.7161, 0.9308, 0.8492]
        )}
        out = normalize_floats(stats)
        for k, s in out.items():
            assert abs(s["score"] - round(s["score"], 4)) < 1e-9, \
                f"{k} score {s['score']} not 4dp"


class TestNormalizeFloatsEdgeCases:
    def test_empty_list_returns_empty(self):
        assert normalize_floats([]) == []

    def test_empty_dict_returns_empty(self):
        assert normalize_floats({}) == {}

    def test_nested_list_of_dicts_recurses(self):
        data = {"outer": [{"v": 1.5}, {"v": 2.75}]}
        out = normalize_floats(data)
        assert abs(out["outer"][0]["v"] - 1.50) < 1e-9

    def test_scalar_passthrough(self):
        assert normalize_floats(3.14) == 3.14
        assert normalize_floats("hello") == "hello"
        assert normalize_floats(42) == 42
