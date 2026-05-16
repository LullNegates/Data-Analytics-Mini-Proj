"""
F3b visualisation -- TAS vs human WR data from f3b_tas_stats.json.

Three charts:
  1. Current gap (s) to TAS per game (games with known TAS reference)
  2. % of theoretical maximum reduction achieved per game
  3. Gap over WR progression timeline for each game (gap history)
"""

from pathlib import Path

import plotext as plt

from charts.helpers import load_json, show_and_wait


def graph_f3b_tas_comparison(path: Path) -> None:
    data = load_json(path)
    games_data = data.get("games", [])
    if not games_data:
        print("  No TAS comparison data in this file. Run analysis/run.py first.")
        return

    # Chart 1 -- current gap to TAS (sorted by gap ascending)
    sorted_games = sorted(games_data, key=lambda g: g["current_gap_s"])
    game_names = [g["game"] for g in sorted_games]
    gaps       = [g["current_gap_s"] for g in sorted_games]
    colors     = ["green" if gap < 1.0 else "yellow" if gap < 30.0 else "red"
                  for gap in gaps]

    plt.bar(game_names, gaps, orientation="h", color=colors)
    plt.title("F3b -- Aktueller Abstand WR zu TAS (Sekunden)")
    plt.xlabel("Abstand in Sekunden (0 = WR entspricht TAS)")
    plt.plotsize(plt.terminal_width(), max(16, len(game_names) + 8))
    show_and_wait("F3b TAS Luecke")

    # Chart 2 -- % of theoretical maximum reduction achieved
    with_pct = [g for g in sorted_games if g.get("pct_closed") is not None]
    if with_pct:
        g_names = [g["game"] for g in with_pct]
        pcts    = [g["pct_closed"] for g in with_pct]
        cols    = ["green" if p >= 95 else "yellow" if p >= 75 else "red"
                   for p in pcts]
        plt.bar(g_names, pcts, orientation="h", color=cols)
        plt.title("F3b -- % der Verbesserung bis zum TAS-Limit bereits erreicht")
        plt.xlabel("% erreicht (100% = WR = TAS)")
        plt.plotsize(plt.terminal_width(), max(16, len(g_names) + 8))
        show_and_wait("F3b % erreicht")

    # Chart 3 -- gap history (timeline) for each game with a TAS reference
    for g in sorted_games:
        history = g.get("gap_history", [])
        if len(history) < 2:
            continue
        wr_nums = [h["wr_number"] for h in history]
        gap_vals = [h["gap_to_tas_s"] for h in history]
        plt.plot(wr_nums, gap_vals, color="cyan")
        plt.title(f"F3b -- WR-zu-TAS-Abstand ueber Zeit: {g['game']}")
        plt.xlabel("WR-Nummer")
        plt.ylabel("Abstand zu TAS (s)")
        plt.plotsize(plt.terminal_width(), 20)
        show_and_wait(g["game"])
