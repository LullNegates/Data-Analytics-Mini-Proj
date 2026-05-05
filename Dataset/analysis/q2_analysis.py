"""
Q2 Statistical Analysis -- Saturation in WR Improvement Over Time

For each eligible game this module:
  1. Fits four models: log, power law, exponential decay, degree-2 polynomial
  2. Selects the best model by AIC (lower = better fit, penalised for complexity)
  3. Estimates the saturation point for exp_decay (days until 95% of max reduction)
  4. Computes the improvement acceleration: is the rate of change speeding up or slowing down?

Model interpretations:
  exp_decay  -- WR times converge on an asymptotic floor (hard lower bound)
  log        -- diminishing returns with no floor (log always keeps decreasing)
  power_law  -- similar to log but better for strongly front-loaded improvement
  poly2      -- baseline; useful only if improvement is U-shaped (unusual)

Reads:  data/clean/q2_saturation.csv
Writes: data/analysis/q2_stats.json
"""

import csv
import json
from pathlib import Path

import numpy as np

from models import fit_all, fit_lowess

CLEAN_DIR    = Path(__file__).parent.parent / "data" / "clean"
ANALYSIS_DIR = Path(__file__).parent.parent / "data" / "analysis"


def _load_csv(name: str) -> list[dict]:
    path = CLEAN_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{name} not found -- run clean.py first")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _analyse_game(game: str, rows: list[dict]) -> dict:
    x = np.array([float(r["days_since_first"]) for r in rows])
    y = np.array([float(r["time_seconds"]) for r in rows])

    fits = fit_all(x, y)
    lowess_r = next((f for f in fits if f.name == "lowess"), None)
    parametric = [f for f in fits if f.name != "lowess"]

    best = parametric[0] if parametric else None

    # Improvement acceleration: fit a line to per-WR improvement sizes over time
    imps = [(float(r["days_since_first"]), float(r["improvement_s"]))
            for r in rows if float(r.get("improvement_s") or 0) > 0]
    acceleration = None
    if len(imps) >= 4:
        xi = np.array([p[0] for p in imps])
        yi = np.array([p[1] for p in imps])
        coeffs = np.polyfit(xi, yi, 1)
        slope = round(float(coeffs[0]), 8)
        acceleration = {
            "slope_s_per_day": slope,
            "interpretation": "decelerating" if slope < 0 else "accelerating",
        }

    # pct_of_total_reduction at each data point (last value = coverage)
    pct_coverage = round(float(rows[-1].get("pct_of_total_reduction", 0)), 2)

    return {
        "game":    game,
        "genre":   rows[0]["genre"],
        "n_wrs":   len(rows),
        "span_days": int(x[-1]),
        "pct_of_reduction_in_dataset": pct_coverage,
        "model_comparison": [f.to_dict() for f in parametric],
        "best_model": best.to_dict() if best else None,
        "lowess_r2": lowess_r.r2 if lowess_r else None,
        "improvement_acceleration": acceleration,
    }


def run() -> dict:
    rows = _load_csv("q2_saturation.csv")
    if not rows:
        print("  [q2] no data -- need at least 5 WRs spanning 2+ years per game")
        return {}

    # Group by game
    by_game: dict[str, list] = {}
    for r in rows:
        by_game.setdefault(r["game"], []).append(r)

    games = [_analyse_game(game, game_rows) for game, game_rows in sorted(by_game.items())]

    # Cross-game: which model wins most often?
    model_wins: dict[str, int] = {}
    for g in games:
        if g["best_model"]:
            name = g["best_model"]["model"]
            model_wins[name] = model_wins.get(name, 0) + 1

    result = {
        "analysis": "q2_saturation",
        "games":       games,
        "model_wins":  model_wins,
        "best_overall_model": max(model_wins, key=model_wins.get) if model_wins else None,
    }

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = ANALYSIS_DIR / "q2_stats.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [q2] written -> {out.name}")
    return result


def print_summary(result: dict) -> None:
    if not result:
        return
    print("\n  Q2 -- Saturation Model Comparison")
    print(f"  {'Game':<42} {'Best Model':<14} {'R2':<8} {'AIC':<10} {'Trend'}")
    print("  " + "-" * 80)
    for g in result["games"]:
        bm    = g["best_model"]
        trend = g["improvement_acceleration"]
        model_name = bm["model"] if bm else "n/a"
        r2    = f"{bm['r2']:.4f}" if bm else "-"
        aic   = f"{bm['aic']:.1f}" if bm else "-"
        acc   = trend["interpretation"] if trend else "n/a"
        print(f"  {g['game']:<42} {model_name:<14} {r2:<8} {aic:<10} {acc}")

    wins = result.get("model_wins", {})
    if wins:
        print(f"\n  Model wins across all games: {wins}")
        print(f"  Best overall model: {result['best_overall_model']}")
