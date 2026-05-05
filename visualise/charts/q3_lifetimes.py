from collections import defaultdict
from pathlib import Path
from statistics import median

import plotext as plt

from charts.helpers import color, load_csv, show_and_wait


def graph_q3_lifetimes(path: Path) -> None:
    rows = load_csv(path)
    if not rows:
        return

    by_genre:  dict[str, list[int]] = defaultdict(list)
    by_decade: dict[str, list[int]] = defaultdict(list)

    for r in rows:
        try:
            d = int(r["duration_days"])
            by_genre[r["genre"]].append(d)
            by_decade[r["decade"]].append(d)
        except (ValueError, KeyError):
            pass

    # Chart 1 — median WR lifetime per genre
    genres  = sorted(by_genre)
    medians = [median(by_genre[g]) for g in genres]
    plt.bar(genres, medians, color=[color(g) for g in genres])
    plt.title("Q3 — Mediane WR-Lebensdauer nach Genre (Tage)")
    plt.xlabel("Genre")
    plt.ylabel("Median (Tage)")
    plt.plotsize(plt.terminal_width(), 24)
    show_and_wait("Genre")

    # Chart 2 — median WR lifetime per decade
    decades  = sorted(by_decade)
    medians2 = [median(by_decade[d]) for d in decades]
    plt.bar(decades, medians2, color="yellow")
    plt.title("Q3 — Mediane WR-Lebensdauer nach Jahrzehnt (Tage)")
    plt.xlabel("Jahrzehnt")
    plt.ylabel("Median (Tage)")
    plt.plotsize(plt.terminal_width(), 24)
    show_and_wait("Jahrzehnt")
