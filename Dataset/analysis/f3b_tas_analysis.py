"""
F3b TAS Analysis -- Human WR vs Tool-Assisted Speedrun Comparison

speedrun.com prohibits TAS submissions on standard leaderboards (site rules).
The canonical TAS archive is TASVideos.org (no public API). TAS reference times
are therefore sourced from a manually curated JSON file (data/reference/tas_known.json).

For games WITH a known TAS reference time this module computes:
  - Current gap (human WR - TAS time) in seconds and as % of first WR
  - Historical gap timeline: how the gap has narrowed across the WR progression
  - Gap closing velocity (s/year) from the last 5 WRs
  - Forward projection: estimated years until human WR matches TAS
  - Model validation: how well the exp_decay/Gompertz asymptote predicts the TAS floor

For games WITHOUT a known TAS time the asymptote-based proxy in q3_analysis.py
(_tas_proximity) is the fallback -- see q3_stats.json -> tas_proximity[].

Academic framing (Wooten 2022 -- "Leaps in Innovation and the Bannister Effect"):
TAS functions as an "existence proof" for a route -- once TAS demonstrates a strategy
is possible, the human RTA community works to adopt it. The gap between TAS and human WR
narrows through route diffusion, not through independent re-discovery. This module
quantifies that diffusion process game by game.

Reads:  data/clean/wr_progression.csv
        data/reference/tas_known.json
        data/analysis/q3_stats.json  (for model floor, if available)
Writes: data/analysis/f3b_tas_stats.json
"""

import csv
import json
import sys
from datetime import date as _date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.DTOs.f3b_dtos import TasComparisonResult, TasGapSnapshot

CLEAN_DIR    = Path(__file__).parent.parent / "data" / "clean"
ANALYSIS_DIR = Path(__file__).parent.parent / "data" / "analysis"
REFERENCE_DIR = Path(__file__).parent.parent / "data" / "reference"


def _load_csv(name: str) -> list[dict]:
    path = CLEAN_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{name} not found -- run clean.py first")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_tas_reference() -> dict:
    path = REFERENCE_DIR / "tas_known.json"
    if not path.exists():
        raise FileNotFoundError("tas_known.json not found in data/reference/")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_model_floors() -> dict[str, float]:
    """Read exp_decay/Gompertz floor estimates from q3_stats.json if it exists."""
    path = ANALYSIS_DIR / "q3_stats.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        q3 = json.load(f)
    floors: dict[str, float] = {}
    for entry in q3.get("tas_proximity", []):
        if entry.get("floor_model") not in (None, "none_detected"):
            floors[entry["game"]] = float(entry["theoretical_floor_s"])
    return floors


def _build_gap_history(wr_rows: list[dict], tas_time_s: float,
                       first_wr_s: float) -> list[TasGapSnapshot]:
    """
    For each WR in the progression, compute the gap to the TAS time.
    Only includes rows where human WR > TAS time (once WR reaches or beats TAS,
    the gap becomes 0 or negative -- we clamp to 0).
    """
    history: list[TasGapSnapshot] = []
    for r in wr_rows:
        wr_s = float(r["time_seconds"])
        gap = max(0.0, wr_s - tas_time_s)
        gap_pct = round(gap / first_wr_s * 100, 3)
        history.append(TasGapSnapshot(
            wr_number  = int(r["wr_number"]),
            date       = r["date"],
            wr_time_s  = round(wr_s, 3),
            gap_to_tas_s = round(gap, 3),
            gap_pct    = gap_pct,
        ))
    return history


def _gap_velocity(wr_rows: list[dict], tas_time_s: float) -> float | None:
    """
    Average pace at which the gap (human WR - TAS) is closing per year.
    Computed from the last min(5, n-1) WRs.
    A positive velocity means the gap is shrinking (good).
    """
    n = len(wr_rows)
    if n < 2:
        return None
    recent_n   = min(5, n - 1)
    older_wr_s = float(wr_rows[-1 - recent_n]["time_seconds"])
    latest_wr_s = float(wr_rows[-1]["time_seconds"])
    older_gap  = max(0.0, older_wr_s  - tas_time_s)
    latest_gap = max(0.0, latest_wr_s - tas_time_s)
    gap_closed = older_gap - latest_gap
    dates = [wr_rows[-1 - recent_n]["date"], wr_rows[-1]["date"]]
    span_days = max(1, (_date.fromisoformat(dates[1]) - _date.fromisoformat(dates[0])).days)
    velocity_per_year = gap_closed / span_days * 365
    return round(velocity_per_year, 4)


def _analyse_game(game: str, wr_rows: list[dict], tas_info: dict,
                  model_floors: dict[str, float]) -> TasComparisonResult | None:
    """Build a TasComparisonResult for one game."""
    tas_time_s = tas_info.get("tas_time_s")
    if tas_time_s is None:
        return None  # no comparable TAS reference for this game

    if len(wr_rows) < 2:
        return None

    first_wr_s   = float(wr_rows[0]["time_seconds"])
    current_wr_s = float(wr_rows[-1]["time_seconds"])

    if tas_time_s >= first_wr_s:
        return None  # TAS reference predates the game's WR history (shouldn't happen)

    current_gap_s  = max(0.0, current_wr_s - tas_time_s)
    current_gap_pct = round(current_gap_s / first_wr_s * 100, 3)

    human_reduction = first_wr_s - current_wr_s
    max_reduction   = first_wr_s - tas_time_s
    pct_closed      = round(human_reduction / max_reduction * 100, 2) if max_reduction > 0 else None

    velocity  = _gap_velocity(wr_rows, tas_time_s)
    est_years = round(current_gap_s / velocity, 1) if velocity and velocity > 0 and current_gap_s > 0 else None

    history = _build_gap_history(wr_rows, tas_time_s, first_wr_s)

    model_floor = model_floors.get(game)
    model_vs_tas = round(float(model_floor) - tas_time_s, 3) if model_floor is not None else None

    return TasComparisonResult(
        game                   = game,
        tas_time_s             = round(tas_time_s, 3),
        tas_source             = tas_info.get("source", "unknown"),
        first_wr_time_s        = round(first_wr_s, 3),
        current_wr_time_s      = round(current_wr_s, 3),
        current_gap_s          = round(current_gap_s, 3),
        current_gap_pct        = current_gap_pct,
        pct_closed             = pct_closed,
        gap_velocity_s_per_year = velocity,
        est_years_to_match_tas = est_years,
        gap_history            = history,
        model_floor_s          = round(float(model_floor), 3) if model_floor else None,
        model_vs_tas_delta_s   = model_vs_tas,
    )


def _cross_game_summary(results: list[TasComparisonResult]) -> dict:
    """
    Aggregate statistics across all games with known TAS comparisons.
    Includes correlation between pct_closed and game age (do older games
    have smaller gaps?), and model accuracy summary.
    """
    if not results:
        return {}

    pct_closed_vals = [r.pct_closed for r in results if r.pct_closed is not None]
    gap_pct_vals    = [r.current_gap_pct for r in results]
    model_deltas    = [r.model_vs_tas_delta_s for r in results if r.model_vs_tas_delta_s is not None]

    summary: dict = {
        "n_games_with_tas":       len(results),
        "mean_gap_pct":           round(float(np.mean(gap_pct_vals)), 3) if gap_pct_vals else None,
        "mean_pct_closed":        round(float(np.mean(pct_closed_vals)), 2) if pct_closed_vals else None,
        "fully_matched_tas":      sum(1 for r in results if r.current_gap_s < 1.0),
        "within_1pct_of_tas":     sum(1 for r in results if r.current_gap_pct < 1.0),
    }

    if model_deltas:
        summary["model_validation"] = {
            "n_games_with_both_model_and_tas": len(model_deltas),
            "mean_model_vs_tas_delta_s": round(float(np.mean(model_deltas)), 3),
            "interpretation": (
                "model overestimates floor (too pessimistic about human limit)"
                if float(np.mean(model_deltas)) > 0
                else "model underestimates floor (too optimistic)"
            ),
        }

    return summary


def run() -> dict:
    wr_prog   = _load_csv("wr_progression.csv")
    tas_ref   = _load_tas_reference()
    model_floors = _load_model_floors()

    # Group WR rows by game (maintaining chronological order from clean.py)
    by_game: dict[str, list] = {}
    for r in wr_prog:
        by_game.setdefault(r["game"], []).append(r)

    tas_games = tas_ref.get("games", {})
    results: list[TasComparisonResult] = []
    skipped: list[dict] = []

    for game, game_rows in sorted(by_game.items()):
        tas_info = tas_games.get(game, {})
        if not tas_info or tas_info.get("tas_time_s") is None:
            skipped.append({"game": game, "reason": tas_info.get("note", "no TAS reference")})
            continue
        result = _analyse_game(game, game_rows, tas_info, model_floors)
        if result:
            results.append(result)

    summary = _cross_game_summary(results)

    output = {
        "analysis":    "f3b_tas_comparison",
        "description": (
            "Human WR vs TAS comparison. TAS times sourced from TASVideos.org. "
            "speedrun.com prohibits TAS on standard leaderboards (no API source). "
            "Games without a comparable TAS reference are listed in 'skipped'."
        ),
        "academic_context": (
            "Wooten (2022, Production and Operations Management) formally models "
            "the Bannister Effect: benchmark innovations stimulate subsequent progress "
            "through route/technique diffusion. TAS serves as that benchmark in speedrunning -- "
            "once TAS demonstrates a strategy, the human community works to adopt it."
        ),
        "games":   [r.to_dict() for r in results],
        "skipped": skipped,
        "summary": summary,
    }

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = ANALYSIS_DIR / "f3b_tas_stats.json"
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [f3b] written -> {out.name}  ({len(results)} games with TAS, {len(skipped)} skipped)")
    return output


def print_summary(result: dict) -> None:
    if not result:
        return
    games = result.get("games", [])
    if not games:
        print("  F3b -- No TAS comparisons available.")
        return
    print("\n  F3b -- TAS vs Human WR Gap")
    print(f"  {'Game':<38} {'TAS(s)':<10} {'WR(s)':<10} {'Gap(s)':<10} {'%Closed':<10} {'Est.yrs'}")
    print("  " + "-" * 85)
    for g in games:
        yrs = f"{g['est_years_to_match_tas']:.1f}" if g['est_years_to_match_tas'] else "--"
        pct = f"{g['pct_closed']:.1f}%" if g['pct_closed'] is not None else "--"
        print(f"  {g['game']:<38} {g['tas_time_s']:<10.1f} {g['current_wr_time_s']:<10.1f} "
              f"{g['current_gap_s']:<10.3f} {pct:<10} {yrs}")

    s = result.get("summary", {})
    if s:
        print(f"\n  Games with TAS: {s['n_games_with_tas']}  |  "
              f"Essentially matched TAS (<1s gap): {s.get('fully_matched_tas', 0)}  |  "
              f"Mean gap: {s.get('mean_gap_pct', 'n/a')}% of first WR")
        mv = s.get("model_validation", {})
        if mv:
            print(f"  Model validation ({mv['n_games_with_both_model_and_tas']} games): "
                  f"mean delta = {mv['mean_model_vs_tas_delta_s']} s ({mv['interpretation']})")
