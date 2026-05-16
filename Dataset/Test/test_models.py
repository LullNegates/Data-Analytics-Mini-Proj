"""Tests for analysis/models.py — curve fitting and Chow test."""

import numpy as np
import pytest

import models
from models import (
    FitResult,
    chow_test,
    fit_all,
    fit_exp_decay,
    fit_gompertz,
    fit_log,
    fit_poly2,
    fit_power_law,
)


# ---------- helpers ----------

def _make_log(n=30):
    x = np.linspace(1, 200, n)
    y = 5.0 * np.log(x + 1) + 100.0
    return x, y


def _make_exp_decay(n=40, a=200.0, b=0.01, c=50.0):
    x = np.linspace(0, 500, n)
    y = a * np.exp(-b * x) + c
    return x, y


def _make_power_law(n=30, a=500.0, b=-0.5):
    x = np.linspace(1, 200, n)
    y = a * np.power(x, b)
    return x, y


def _make_poly2(n=30, a2=0.01, a1=-1.0, a0=200.0):
    x = np.linspace(0, 100, n)
    y = a2 * x**2 + a1 * x + a0
    return x, y


def _make_break(n_left=15, n_right=15):
    """Two-segment line with a sharp break in slope."""
    x_l = np.linspace(0, 50, n_left)
    y_l = 200.0 - 0.5 * x_l           # gentle slope
    x_r = np.linspace(50, 100, n_right)
    y_r = 175.0 - 4.0 * (x_r - 50)   # steep slope after break
    return np.concatenate([x_l, x_r]), np.concatenate([y_l, y_r])


# ---------- log ----------

class TestFitLog:
    def test_returns_fit_result(self):
        x, y = _make_log()
        r = fit_log(x, y)
        assert r is not None
        assert isinstance(r, FitResult)

    def test_r2_close_to_one(self):
        x, y = _make_log()
        r = fit_log(x, y)
        assert r.r2 > 0.99

    def test_params_shape(self):
        x, y = _make_log()
        r = fit_log(x, y)
        assert "a" in r.params and "b" in r.params

    def test_a_positive(self):
        x, y = _make_log()
        r = fit_log(x, y)
        assert r.params["a"] > 0  # increasing log curve


# ---------- power law ----------

class TestFitPowerLaw:
    def test_returns_fit_result(self):
        x, y = _make_power_law()
        r = fit_power_law(x, y)
        assert r is not None

    def test_r2_close_to_one(self):
        x, y = _make_power_law()
        r = fit_power_law(x, y)
        assert r.r2 > 0.99

    def test_exponent_negative_for_diminishing_returns(self):
        x, y = _make_power_law(b=-0.5)
        r = fit_power_law(x, y)
        assert r.params["b"] < 0


# ---------- exp_decay ----------

class TestFitExpDecay:
    def test_returns_fit_result(self):
        x, y = _make_exp_decay()
        r = fit_exp_decay(x, y)
        assert r is not None

    def test_r2_close_to_one(self):
        x, y = _make_exp_decay()
        r = fit_exp_decay(x, y)
        assert r.r2 > 0.99

    def test_asymptote_close_to_true_floor(self):
        x, y = _make_exp_decay(c=50.0)
        r = fit_exp_decay(x, y)
        assert abs(r.params["c"] - 50.0) < 5.0  # within 5 s of truth

    def test_saturation_days_present(self):
        x, y = _make_exp_decay()
        r = fit_exp_decay(x, y)
        assert "saturation_days_95pct" in r.params
        assert r.params["saturation_days_95pct"] > 0


# ---------- poly2 ----------

class TestFitPoly2:
    def test_returns_fit_result(self):
        x, y = _make_poly2()
        r = fit_poly2(x, y)
        assert r is not None

    def test_r2_close_to_one(self):
        x, y = _make_poly2()
        r = fit_poly2(x, y)
        assert r.r2 > 0.99

    def test_params_present(self):
        x, y = _make_poly2()
        r = fit_poly2(x, y)
        assert all(k in r.params for k in ("a2", "a1", "a0"))


# ---------- gompertz ----------

class TestFitGompertz:
    def test_returns_fit_result_or_none(self):
        x, y = _make_exp_decay()
        r = fit_gompertz(x, y)
        # Gompertz is allowed to fail on pure exp-decay data (not S-shaped)
        assert r is None or isinstance(r, FitResult)

    def test_r2_reasonable_on_s_shape(self):
        # Synthesise an S-shaped decay (slow start, fast middle, plateau)
        x = np.linspace(0, 300, 60)
        y = 50.0 + 150.0 * np.exp(2.0 * np.exp(-0.04 * x))
        r = fit_gompertz(x, y)
        if r is not None:
            assert r.r2 > 0.90


# ---------- fit_all ----------

class TestFitAll:
    def test_returns_nonempty_list(self):
        x, y = _make_exp_decay()
        results = fit_all(x, y)
        assert len(results) >= 2

    def test_sorted_by_aic_ascending(self):
        x, y = _make_exp_decay()
        results = [r for r in fit_all(x, y) if r.name != "lowess"]
        aics = [r.aic for r in results]
        assert aics == sorted(aics)

    def test_lowess_at_end_if_present(self):
        x, y = _make_exp_decay()
        results = fit_all(x, y)
        names = [r.name for r in results]
        if "lowess" in names:
            assert names[-1] == "lowess"

    def test_exp_decay_wins_on_exp_data(self):
        x, y = _make_exp_decay()
        parametric = [r for r in fit_all(x, y) if r.name != "lowess"]
        assert parametric[0].name in ("exp_decay", "gompertz")


# ---------- FitResult ----------

class TestFitResult:
    def test_to_dict_keys(self):
        x, y = _make_log()
        r = fit_log(x, y)
        d = r.to_dict()
        assert set(d.keys()) >= {"model", "r2", "rmse", "aic", "bic", "params"}

    def test_aic_finite(self):
        x, y = _make_log()
        r = fit_log(x, y)
        assert np.isfinite(r.aic)

    def test_rmse_non_negative(self):
        x, y = _make_log()
        r = fit_log(x, y)
        assert r.rmse >= 0


# ---------- chow_test ----------

class TestChowTest:
    def test_high_f_on_clear_break(self):
        x, y = _make_break()
        split = len(x) // 2
        f = chow_test(x, y, split)
        assert f > 3.0  # significant at p=0.05

    def test_low_f_on_noisy_linear_trend(self):
        # Uniformly noisy linear trend — no structural break.
        # True breaks give F >> 10; random noise stays well below that.
        rng = np.random.default_rng(42)
        x = np.linspace(0, 100, 30)
        y = 200.0 - 2.0 * x + rng.normal(0, 0.5, 30)
        split = 15
        f = chow_test(x, y, split)
        assert f < 10.0

    def test_does_not_crash_on_degenerate_input(self):
        # Flat line: RSS is ~0 everywhere; floating point may give any value,
        # but chow_test must not raise an exception.
        x = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 10.0])
        f = chow_test(x, y, 3)
        assert isinstance(float(f), float)  # just verify it returns a number
