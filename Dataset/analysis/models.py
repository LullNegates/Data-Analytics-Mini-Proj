"""
Curve fitting models for WR progression analysis.

Available models: log, power_law, exp_decay, poly2, gompertz, lowess.
Each parametric fit returns a FitResult with R2, RMSE, AIC, BIC, and named params.
fit_all() runs every model and returns results sorted by AIC (lower = better).

Why AIC, not R2: R2 always rises when you add parameters, so it would always pick
the most flexible model regardless of whether the extra flexibility is justified.
AIC penalises each parameter (+2 per param), so a complex model only wins when its
fit improves enough to overcome the complexity penalty -- which is exactly the
question we want to answer for saturation analysis.
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
        # Saturation estimate: days until WR time is within 5% of the asymptote c.
        # Solving a*exp(-b*x) = 0.05*a  =>  x = -ln(0.05) / b
        # Interpreted as the "theoretical limit date" -- the point at which continued
        # improvement would be smaller than typical run-to-run variance.
        a, b, c = popt
        if b > 0 and a > 0:
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
    Gompertz is included: it beats exp_decay on S-shaped saturation curves.
    """
    parametric = [fit_log, fit_power_law, fit_exp_decay, fit_poly2, fit_gompertz]
    results = [r for fn in parametric for r in [fn(x, y)] if r is not None]
    results.sort(key=lambda r: r.aic)
    lowess_r = fit_lowess(x, y)
    if lowess_r:
        results.append(lowess_r)
    return results

def fit_gompertz(x: np.ndarray, y: np.ndarray) -> "FitResult | None":
    """
    Gompertz decay curve adapted for decreasing WR times:
    y = floor + amplitude * exp(b * exp(-c * x))

    Reduces to: starts at floor + amplitude*exp(b) at x=0, decays to floor as x→∞.
    This is the 'reflected' Gompertz, modelling asymmetric S-shaped decay toward a
    hard floor -- appropriate when improvement was slow early, accelerated after a
    glitch discovery, then plateaued. The 4-parameter form (vs exp_decay's 3) captures
    the S-shape; AIC will penalise the extra parameter, so Gompertz only wins when the
    S-shape provides a materially better fit.
    """
    def func(t, amplitude, b, c, floor):
        return floor + amplitude * np.exp(b * np.exp(-c * t))
    try:
        floor0    = float(np.min(y))
        amp0      = float(np.max(y) - np.min(y))
        span      = float(np.max(x)) + 1
        p0 = [amp0, 1.0, 3.0 / span, floor0]
        popt, _ = curve_fit(func, x, y, p0=p0,
                            bounds=([0, 0, 0, 0], [np.inf, np.inf, np.inf, np.inf]),
                            maxfev=10000)
        y_pred = func(x, *popt)
        return FitResult("gompertz",
                         {"amplitude": round(float(popt[0]), 6),
                          "b":         round(float(popt[1]), 6),
                          "c":         round(float(popt[2]), 8),
                          "floor":     round(float(popt[3]), 6)},
                         y_pred, y, 4)
    except Exception:
        return None

def chow_test(x: np.ndarray, y: np.ndarray, split_idx: int) -> float:
    """
    Compute the Chow Test F-statistic for a structural break at split_idx.

    The test asks: is the data better described by one linear regression or by two
    separate regressions -- one before split_idx and one after?

    F = [ (RSS_pooled - (RSS1 + RSS2)) / k ] / [ (RSS1 + RSS2) / (N - 2k) ]

    where k=2 (parameters per linear fit), RSS_pooled is the residual sum of squares
    for the single pooled fit, and RSS1+RSS2 is the combined residual for the two-segment
    fit. A high F means the two-segment model fits substantially better than the one --
    evidence that the data has a different slope after the split point (new glitch,
    route change, patch). Critical value at p=0.05 for large N: F(2, inf) ≈ 3.00.
    """
    def _get_rss(tx, ty):
        if len(tx) < 3: return 1e10
        coeffs = np.polyfit(tx, ty, 1)
        return np.sum((ty - np.polyval(coeffs, tx))**2)

    rss_pooled = _get_rss(x, y)
    rss_left = _get_rss(x[:split_idx], y[:split_idx])
    rss_right = _get_rss(x[split_idx:], y[split_idx:])
    
    k = 2 # parameters for linear fit
    n1, n2 = split_idx, len(x) - split_idx
    numerator = (rss_pooled - (rss_left + rss_right)) / k
    denominator = (rss_left + rss_right) / (n1 + n2 - 2 * k)
    return numerator / denominator if denominator > 0 else 0
