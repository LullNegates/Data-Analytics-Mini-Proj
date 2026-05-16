"""
F3a visualisation -- post-breakthrough dynamics from q3_stats.json.

Two charts:
  1. Flattening ratio per game (how much slower is post-breakthrough improvement)
  2. Breakthrough magnitude as % of total WR reduction per game
"""

from pathlib import Path

import plotext as plt

from charts.helpers import load_json, show_and_wait


def graph_f3a_post_breakthrough(path: Path) -> None:
    data = load_json(path)
    entries = data.get("post_breakthrough_dynamics", [])
    if not entries:
        print("  No post_breakthrough_dynamics in this file.")
        return

    # Sort by flattening_ratio ascending (most flattened first)
    entries_with_ratio = [e for e in entries if e.get("flattening_ratio") is not None]
    entries_with_ratio.sort(key=lambda e: e["flattening_ratio"])

    games  = [e["game"] for e in entries_with_ratio]
    ratios = [e["flattening_ratio"] for e in entries_with_ratio]
    colors = [
        "red"    if r < 0.5  else
        "yellow" if r < 1.0  else
        "green"
        for r in ratios
    ]

    # Chart 1 — flattening ratio
    plt.bar(games, ratios, orientation="h", color=colors)
    plt.title("F3a -- Flattening Ratio nach Durchbruch (rot < 0.5 = Plateau)")
    plt.xlabel("Flattening Ratio (post/pre Verbesserungsrate)")
    plt.plotsize(plt.terminal_width(), max(20, len(games) + 8))
    show_and_wait("F3a Flattening Ratio")

    # Chart 2 — breakthrough magnitude as % of total
    entries_with_pct = [e for e in entries if e.get("breakthrough_pct_of_total") is not None]
    entries_with_pct.sort(key=lambda e: -e["breakthrough_pct_of_total"])
    games2 = [e["game"] for e in entries_with_pct]
    pcts   = [e["breakthrough_pct_of_total"] for e in entries_with_pct]

    plt.bar(games2, pcts, orientation="h", color="cyan")
    plt.title("F3a -- Groesster Einzeldurchbruch als % der Gesamtreduktion")
    plt.xlabel("% der Gesamtreduktion")
    plt.plotsize(plt.terminal_width(), max(20, len(games2) + 8))
    show_and_wait("F3a Durchbruchstaerke")
