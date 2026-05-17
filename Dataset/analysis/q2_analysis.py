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
import sys
from pathlib import Path

import numpy as np

from models import fit_all, fit_lowess, chow_test

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.DTOs.q2_dtos import (ImprovementAccelerationResult,
                                  StructuralBreakResult, GameQ2Result)

CLEAN_DIR    = Path(__file__).parent.parent / "data" / "clean"
ANALYSIS_DIR = Path(__file__).parent.parent / "data" / "analysis"


def _load_csv(name: str) -> list[dict]:
    path = CLEAN_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{name} not found -- run clean.py first")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _detect_structural_break(x: np.ndarray, y: np.ndarray,
                             rows: list[dict]) -> StructuralBreakResult | None:
    """
    Scan all valid split points and return the one with the highest Chow Test F-statistic.

    A high F-statistic means the data is better described by two separate linear regressions
    than one -- evidence of a paradigm shift (new glitch, route discovery, tool/technique change).
    Requires at least 3 points on each side of the split for a valid regression.
    F critical value at p=0.05: F(2, inf) = 3.00; we use 3.0 as a conservative threshold.
    """
    MIN_EACH_SIDE = 3
    if len(x) < MIN_EACH_SIDE * 2 + 1:
        return None

    best_f, best_idx = 0.0, None
    for split_idx in range(MIN_EACH_SIDE, len(x) - MIN_EACH_SIDE):
        f = chow_test(x, y, split_idx)
        if f > best_f:
            best_f, best_idx = f, split_idx

    if best_idx is None:
        return None

    return StructuralBreakResult(
        split_wr_number  = int(rows[best_idx]["wr_number"]),
        split_date       = rows[best_idx]["date"],
        f_statistic      = round(float(best_f), 4),
        significant_at_005 = bool(best_f > 3.0),
    )


def _analyse_game(game: str, rows: list[dict]) -> GameQ2Result:
    """
    Fit all curve models to one game's WR time series and detect structural breaks.

    x = days_since_first (elapsed time), y = time_seconds (WR time).
    AIC selects the best parametric model. If exp_decay or Gompertz wins, the game
    is converging on a theoretical minimum; if log or power_law wins, it is still
    improving without an obvious floor. Also computes improvement acceleration
    (is each successive WR saving more or less time?) and the most likely structural
    break point via the Chow Test.
    """
    x = np.array([float(r["days_since_first"]) for r in rows])
    y = np.array([float(r["time_seconds"]) for r in rows])

    fits = fit_all(x, y)
    lowess_r  = next((f for f in fits if f.name == "lowess"), None)
    parametric = [f for f in fits if f.name != "lowess"]
    best = parametric[0] if parametric else None

    # Improvement acceleration: linear slope of per-WR improvement sizes over time.
    # A negative slope means each new WR saves less time than the previous one --
    # the classic saturation signature. A positive slope means improvements are
    # growing, signalling an active discovery or optimisation phase.
    imps = [(float(r["days_since_first"]), float(r["improvement_s"]))
            for r in rows if float(r.get("improvement_s") or 0) > 0]
    acceleration: ImprovementAccelerationResult | None = None
    if len(imps) >= 4:
        xi    = np.array([p[0] for p in imps])
        yi    = np.array([p[1] for p in imps])
        slope = round(float(np.polyfit(xi, yi, 1)[0]), 8)
        acceleration = ImprovementAccelerationResult(
            slope_s_per_day = slope,
            interpretation  = "decelerating" if slope < 0 else "accelerating",
        )

    return GameQ2Result(
        game                        = game,
        genre                       = rows[0]["genre"],
        n_wrs                       = len(rows),
        span_days                   = int(x[-1]),
        pct_of_reduction_in_dataset = round(float(rows[-1].get("pct_of_total_reduction", 0)), 2),
        model_comparison            = [f.to_dict() for f in parametric],
        best_model                  = best.to_dict() if best else None,
        lowess_r2                   = lowess_r.r2 if lowess_r else None,
        improvement_acceleration    = acceleration,
        structural_break            = _detect_structural_break(x, y, rows),
    )


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
        if g.best_model:
            name = g.best_model["model"]
            model_wins[name] = model_wins.get(name, 0) + 1

    result = {
        "analysis":           "q2_saturation",
        "games":              [g.to_dict() for g in games],
        "model_wins":         model_wins,
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
    print(f"  {'Game':<38} {'Best Model':<12} {'R2':<8} {'Trend':<14} {'Break?'}")
    print("  " + "-" * 82)
    for g in result["games"]:
        bm    = g["best_model"]
        trend = g["improvement_acceleration"]
        brk   = g.get("structural_break")
        model_name = bm["model"] if bm else "n/a"
        r2    = f"{bm['r2']:.4f}" if bm else "-"
        acc   = trend["interpretation"] if trend else "n/a"
        brk_str = f"WR#{brk['split_wr_number']} ({brk['split_date'][:7]})" if brk and brk["significant_at_0.05"] else "-"
        print(f"  {g['game']:<38} {model_name:<12} {r2:<8} {acc:<14} {brk_str}")

    wins = result.get("model_wins", {})
    if wins:
        print(f"\n  Model wins across all games: {wins}")
        print(f"  Best overall model: {result['best_overall_model']}")
