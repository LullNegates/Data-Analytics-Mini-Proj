from collections import defaultdict
from pathlib import Path

import plotext as plt

from charts.helpers import color, load_csv, parse_date, show_and_wait


def graph_wr_progression(path: Path) -> None:
    rows = load_csv(path)
    if not rows:
        return

    by_game: dict[str, list] = defaultdict(list)
    genre_of: dict[str, str] = {}
    for r in rows:
        by_game[r["game"]].append(r)
        genre_of[r["game"]] = r["genre"]

    games = list(by_game)
    total = len(games)

    for i, game in enumerate(games, 1):
        entries = by_game[game]
        pairs = [
            (d.strftime("%Y-%m-%d"), float(e["time_seconds"]) / 60)
            for e in entries
            if (d := parse_date(e["date"]))
        ]
        if not pairs:
            continue

        dates, times = zip(*pairs)
        plt.date_form("Y-m-d")
        plt.plot(list(dates), list(times), color=color(genre_of[game]))
        plt.title(f"WR-Verlauf: {game}  [{genre_of[game]}]  ({i}/{total})")
        plt.xlabel("Datum")
        plt.ylabel("WR-Zeit (Minuten)")
        plt.plotsize(plt.terminal_width(), 28)
        show_and_wait(f"{i}/{total}")
