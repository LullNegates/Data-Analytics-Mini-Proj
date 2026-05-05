from collections import defaultdict
from pathlib import Path

import plotext as plt

from charts.helpers import color, load_csv, parse_date, show_and_wait


def graph_all_runs(path: Path) -> None:
    rows = load_csv(path)
    if not rows:
        return

    by_genre: dict[str, list[float]] = defaultdict(list)
    year_counts: dict[int, int] = defaultdict(int)

    for r in rows:
        try:
            by_genre[r["genre"]].append(float(r["time_seconds"]) / 60)
        except (ValueError, KeyError):
            pass
        d = parse_date(r.get("date", ""))
        if d and 1980 <= d.year <= 2030:
            year_counts[d.year] += 1

    # Chart 1 — run time distribution per genre (overlapping histograms)
    for genre, times in sorted(by_genre.items()):
        plt.hist(times, bins=40, label=genre, color=color(genre))
    plt.title("Verteilung aller Runs nach Laufzeit (Minuten)")
    plt.xlabel("Laufzeit (Min.)")
    plt.ylabel("Anzahl Runs")
    plt.plotsize(plt.terminal_width(), 28)
    show_and_wait("Zeitverteilung")

    # Chart 2 — total runs per year
    years = sorted(year_counts)
    counts = [year_counts[y] for y in years]
    plt.bar(years, counts, color="cyan")
    plt.title("Anzahl Runs pro Jahr (alle Spiele)")
    plt.xlabel("Jahr")
    plt.ylabel("Runs")
    plt.plotsize(plt.terminal_width(), 24)
    show_and_wait("Runs/Jahr")
