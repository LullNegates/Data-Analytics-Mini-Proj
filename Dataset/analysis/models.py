"""
Curve fitting models for WR progression analysis.

Available models: log, power_law, exp_decay, poly2
Each returns a FitResult with R2, RMSE, AIC, BIC, and named params.
fit_all() runs every model and returns results sorted by AIC (best first).
"""

import numpy as np
from scipy.optimize import curve_fit


# ---------- information criteria ----------

def _rss(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sum((y_true - y_pred) ** 2))


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    return 1.0 - _rss(y_true, y_pred) / ss_tot if ss_tot > 0 else 0.0


def _aic(n: int, rss: float, k: int) -> float:
    """Akaike Information Criterion -- lower is better, penalises complexity."""
    if rss <= 0 or n <= 0:
        return float("inf")
    return n * np.log(rss / n) + 2 * k


def _bic(n: int, rss: float, k: int) -> float:
    """Bayesian Information Criterion -- stronger complexity penalty than AIC."""
    if rss <= 0 or n <= 0:
        return float("inf")
    return n * np.log(rss / n) + k * np.log(n)


# ---------- result container ----------

class FitResult:
    """Holds the outcome of one curve fit."""

    def __init__(self, name: str, params: dict, y_pred: np.ndarray,
                 y_true: np.ndarray, n_params: int):
        self.name = name
        self.params = params
        n = len(y_true)
        rss = _rss(y_true, y_pred)
        self.r2   = round(_r2(y_true, y_pred), 6)
        self.rmse = round(float(np.sqrt(rss / n)), 4) if n > 0 else None
        self.aic  = round(_aic(n, rss, n_params), 3)
        self.bic  = round(_bic(n, rss, n_params), 3)
        self._y_pred = y_pred

    def summary(self) -> str:
        return (f"{self.name:<14} R2={self.r2:.4f}  RMSE={self.rmse:.3f}"
                f"  AIC={self.aic:.1f}  BIC={self.bic:.1f}")

    def to_dict(self) -> dict:
        return {
            "model":  self.name,
            "r2":     self.r2,
            "rmse":   self.rmse,
            "aic":    self.aic,
            "bic":    self.bic,
            "params": self.params,
        }


# ---------- model functions ----------

def fit_log(x: np.ndarray, y: np.ndarray) -> "FitResult | None":
    """y = a * ln(x + 1) + b  (classic log saturation curve)"""
    def _f(x, a, b):
        return a * np.log(x + 1) + b
    try:
        popt, _ = curve_fit(_f, x, y, maxfev=8000)
        return FitResult("log", {"a": round(float(popt[0]), 6), "b": round(float(popt[1]), 6)},
                         _f(x, *popt), y, 2)
    except Exception:
        return None


def fit_power_law(x: np.ndarray, y: np.ndarray) -> "FitResult | None":
    """
    y = a * x^b  (power law -- linearises as ln(y) = ln(a) + b*ln(x))
    Exponent b < 0 means diminishing returns.
    """
    x_safe = np.where(x <= 0, 1e-9, x)
    def _f(x, a, b):
        return a * np.power(np.abs(x), b)
    try:
        popt, _ = curve_fit(_f, x_safe, y, p0=[float(y[0]), -0.3], maxfev=8000)
        return FitResult("power_law",
                         {"a": round(float(popt[0]), 6), "b": round(float(popt[1]), 6)},
                         _f(x_safe, *popt), y, 2)
    except Exception:
        return None


def fit_exp_decay(x: np.ndarray, y: np.ndarray) -> "FitResult | None":
    """
    y = a * exp(-b * x) + c  (asymptotic decay toward floor c)
    Best model when WR times approach a hard lower bound.
    Saturation point: x where y is within 5% of asymptote c.
    """
    a0 = float(np.max(y) - np.min(y))
    c0 = float(np.min(y))
    b0 = 1.0 / (float(np.max(x)) + 1)
    def _f(x, a, b, c):
        return a * np.exp(-b * x) + c
    try:
        popt, _ = curve_fit(_f, x, y, p0=[a0, b0, c0],
                            bounds=([0, 1e-9, 0], [np.inf, np.inf, np.inf]),
                            maxfev=12000)
        r = FitResult("exp_decay",
                      {"a": round(float(popt[0]), 6),
                       "b": round(float(popt[1]), 8),
                       "c": round(float(popt[2]), 6)},
                      _f(x, *popt), y, 3)
        # Attach saturation estimate: days until within 5% of asymptote
        a, b, c = popt
        if b > 0 and a > 0:
            sat_days = float(-np.log(0.05 * a / a) / b) if a > 0 else None
            # Correct formula: y = c + 0.05*a  =>  0.05 = exp(-b*x)  =>  x = -ln(0.05)/b
            sat_days = round(float(-np.log(0.05) / b), 1)
            r.params["saturation_days_95pct"] = sat_days
        return r
    except Exception:
        return None


def fit_poly2(x: np.ndarray, y: np.ndarray) -> "FitResult | None":
    """Degree-2 polynomial -- captures parabolic curves, useful as a baseline."""
    try:
        coeffs = np.polyfit(x, y, 2)
        y_pred = np.polyval(coeffs, x)
        return FitResult("poly2",
                         {"a2": round(float(coeffs[0]), 8),
                          "a1": round(float(coeffs[1]), 6),
                          "a0": round(float(coeffs[2]), 6)},
                         y_pred, y, 3)
    except Exception:
        return None


def fit_lowess(x: np.ndarray, y: np.ndarray, frac: float = 0.3) -> "FitResult | None":
    """
    LOWESS non-parametric smoother -- no formula, but highest fidelity.
    Used to detect regime changes and inflection points visually.
    frac: fraction of data used in each local regression (0.15-0.4 typical).
    """
    try:
        from statsmodels.nonparametric.smoothers_lowess import lowess
        smoothed = lowess(y, x, frac=frac, it=3, return_sorted=False)
        return FitResult("lowess", {"frac": frac}, smoothed, y, int(len(x) * frac))
    except ImportError:
        return None
    except Exception:
        return None


# ---------- model comparison ----------

def fit_all(x: np.ndarray, y: np.ndarray) -> list[FitResult]:
    """
    Fit all parametric models plus LOWESS.
    Returns list sorted by AIC ascending (best model first).
    LOWESS is excluded from ranking (non-parametric, no meaningful AIC).
    """
    parametric = [fit_log, fit_power_law, fit_exp_decay, fit_poly2]
    results = [r for fn in parametric for r in [fn(x, y)] if r is not None]
    results.sort(key=lambda r: r.aic)
    lowess_r = fit_lowess(x, y)
    if lowess_r:
        results.append(lowess_r)
    return results
