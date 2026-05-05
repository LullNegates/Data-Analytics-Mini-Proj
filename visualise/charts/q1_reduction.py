from pathlib import Path
from collections import defaultdict

import plotext as plt

from charts.helpers import load_csv, show_and_wait, color


def graph_q1_reduction(path: Path) -> None:
    rows = load_csv(path)
    if not rows:
        return

    # already sorted by pct_reduction descending from clean.py
    games  = [r["game"] for r in rows]
    pcts   = [float(r["pct_reduction"]) for r in rows]
    genres = [r["genre"] for r in rows]

    plt.bar(games, pcts, orientation="h", color=[color(g) for g in genres])
    plt.title("Q1 — Prozentuale Zeitreduktion je Spielkategorie")
    plt.xlabel("% Reduktion")
    plt.plotsize(plt.terminal_width(), max(20, len(games) + 6))
    show_and_wait("Q1 Reduktion")
