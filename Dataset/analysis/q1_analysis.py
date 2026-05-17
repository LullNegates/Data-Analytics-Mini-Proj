"""
Q1 Statistical Analysis -- Percentage Time Reduction per Game Category

Beyond the raw % reduction, this module computes:
  - Power law fit to per-WR improvement sizes (does each new WR save less time?)
  - Improvement velocity trend (accelerating or decelerating over time?)
  - WR density and median improvement per genre
  - Kruskal-Wallis test: are annual improvement rates significantly different across genres?

Reads:  data/clean/q1_reduction.csv, data/clean/wr_progression.csv
Writes: data/analysis/q1_stats.json
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import kruskal, spearmanr

from models import fit_power_law, fit_log, FitResult

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.DTOs.q1_dtos import VelocityTrendResult

CLEAN_DIR   = Path(__file__).parent.parent / "data" / "clean"
ANALYSIS_DIR = Path(__file__).parent.parent / "data" / "analysis"


def _load_csv(name: str) -> list[dict]:
    path = CLEAN_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{name} not found in data/clean/ -- run clean.py first")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _power_law_on_improvements(wr_rows: list[dict]) -> FitResult | None:
    """
    Fit a power law to per-WR improvement sizes for one game.
    x = WR number (1, 2, 3, ...), y = seconds saved by that WR.
    Exponent b < 0 confirms diminishing returns pattern.
    Returns FitResult directly; callers call .to_dict() at the serialisation boundary.
    """
    improvements = []
    for r in wr_rows:
        if float(r.get("improvement_s") or 0) > 0:
            improvements.append(float(r["improvement_s"]))
    if len(improvements) < 4:
        return None
    x = np.arange(1, len(improvements) + 1, dtype=float)
    y = np.array(improvements)
    result = fit_power_law(x, y)
    if result is None:
        result = fit_log(x, y)
    return result


def _velocity_trend(wr_rows: list[dict]) -> VelocityTrendResult:
    """
    Spearman correlation between WR date and per-WR improvement size.
    rho < 0 => improvements are shrinking over time (saturation).
    rho > 0 => improvements are growing (community is accelerating).

    Spearman (not Pearson) because improvement sizes are right-skewed: a single
    glitch discovery can save orders of magnitude more time than a typical WR.
    Pearson's r is sensitive to those outliers and would misrepresent the general
    trend. Spearman's rho works on ranks, making it robust to extreme values.
    """
    pairs = [(r["date"], float(r.get("improvement_s") or 0))
             for r in wr_rows if r.get("improvement_s")]
    if len(pairs) < 4:
        return VelocityTrendResult(rho=None, pvalue=None, interpretation="insufficient_data")
    dates  = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    from datetime import date
    x = np.array([(date.fromisoformat(d) - date.fromisoformat(dates[0])).days for d in dates], dtype=float)
    y = np.array(values)
    rho, pval = spearmanr(x, y)
    if abs(rho) < 0.2:
        interp = "no_trend"
    elif rho < 0:
        interp = "decelerating"
    else:
        interp = "accelerating"
    return VelocityTrendResult(
        rho=round(float(rho), 4),
        pvalue=round(float(pval), 4),
        interpretation=interp,
    )


def run() -> dict:
    q1_rows = _load_csv("q1_reduction.csv")
    wr_rows = _load_csv("wr_progression.csv")

    # Group WR rows by game for per-game analysis
    wr_by_game: dict[str, list] = {}
    for r in wr_rows:
        wr_by_game.setdefault(r["game"], []).append(r)

    # --- Per-game stats ---
    games = []
    for r in q1_rows:
        game_wrs = wr_by_game.get(r["game"], [])
        total_runs = max(float(r.get("total_runs") or 1), 1)
        wr_count   = float(r.get("wr_count") or 0)
        pl_fit = _power_law_on_improvements(game_wrs)
        vt     = _velocity_trend(game_wrs)
        games.append({
            "game":               r["game"],
            "genre":              r["genre"],
            "pct_reduction":      float(r["pct_reduction"]),
            "annual_rate_pct":    float(r["annual_rate_pct"]),
            "wr_density_per_year": float(r["wr_density_per_year"]),
            "improvement_velocity_s_per_day": float(r["improvement_velocity_s_per_day"]),
            "median_improvement_s": float(r["median_improvement_s"]),
            # Fraction of all submitted runs that set a new WR.
            # Low wr_rate = record is hard to break relative to total attempts (saturation signal).
            # High wr_rate = community was actively improving at a high success rate.
            "wr_rate":            round(wr_count / total_runs, 6),
            "power_law_fit":      pl_fit.to_dict() if pl_fit is not None else None,
            "velocity_trend":     vt.to_dict(),
        })

    # --- Genre aggregation ---
    genre_stats: dict[str, dict] = {}
    for g in games:
        genre = g["genre"]
        genre_stats.setdefault(genre, {"annual_rates": [], "densities": [], "pct_reductions": [], "wr_rates": []})
        genre_stats[genre]["annual_rates"].append(g["annual_rate_pct"])
        genre_stats[genre]["densities"].append(g["wr_density_per_year"])
        genre_stats[genre]["pct_reductions"].append(g["pct_reduction"])
        genre_stats[genre]["wr_rates"].append(g["wr_rate"])

    genre_summary = {}
    for genre, data in genre_stats.items():
        rates = np.array(data["annual_rates"])
        wr_rates = np.array(data.get("wr_rates", []))
        genre_summary[genre] = {
            "game_count":        len(rates),
            "mean_annual_rate":  round(float(np.mean(rates)), 4),
            "median_annual_rate": round(float(np.median(rates)), 4),
            "mean_pct_reduction": round(float(np.mean(data["pct_reductions"])), 4),
            "mean_wr_density":   round(float(np.mean(data["densities"])), 3),
            "mean_wr_rate":      round(float(np.mean(wr_rates)), 6) if len(wr_rates) > 0 else None,
        }

    # --- Kruskal-Wallis test across genres ---
    # H0: annual improvement rates are drawn from the same distribution across genres
    groups = [np.array(v["annual_rates"]) for v in genre_stats.values() if len(v["annual_rates"]) >= 2]
    kw_result = {"stat": None, "pvalue": None, "significant_at_0.05": None, "note": "need >= 2 games per genre"}
    if len(groups) >= 2:
        try:
            stat, pval = kruskal(*groups)
            kw_result = {
                "stat":               round(float(stat), 4),
                "pvalue":             round(float(pval), 4),
                "significant_at_0.05": bool(pval < 0.05),
                "interpretation":     (
                    "Annual improvement rates differ significantly across genres"
                    if pval < 0.05 else
                    "No significant difference in annual improvement rates across genres"
                ),
            }
        except Exception as e:
            kw_result["note"] = str(e)

    result = {
        "analysis": "q1_pct_reduction",
        "games":         games,
        "genre_summary": genre_summary,
        "kruskal_wallis_annual_rate": kw_result,
    }

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = ANALYSIS_DIR / "q1_stats.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [q1] written -> {out.name}")
    return result


def print_summary(result: dict) -> None:
    print("\n  Q1 -- Genre Improvement Rate Summary")
    print(f"  {'Genre':<18} {'Mean Annual %':<16} {'Median Annual %':<18} {'Mean WR/yr'}")
    print("  " + "-" * 65)
    for genre, s in sorted(result["genre_summary"].items(), key=lambda x: -x[1]["mean_annual_rate"]):
        print(f"  {genre:<18} {s['mean_annual_rate']:<16.2f} {s['median_annual_rate']:<18.2f} {s['mean_wr_density']:.2f}")

    kw = result["kruskal_wallis_annual_rate"]
    if kw.get("pvalue") is not None:
        sig = "YES" if kw["significant_at_0.05"] else "no"
        print(f"\n  Kruskal-Wallis (genres differ?): p={kw['pvalue']}  significant={sig}")

    decelerating = [g["game"] for g in result["games"]
                    if g["velocity_trend"]["interpretation"] == "decelerating"]
    if decelerating:
        print(f"\n  Games showing decelerating improvement (saturation likely):")
        for g in decelerating:
            print(f"    - {g}")
