from collections import defaultdict
from pathlib import Path

import numpy as np
import plotext as plt

from charts.helpers import color, load_csv, show_and_wait


def graph_q2_saturation(path: Path) -> None:
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
        x = [float(e["days_since_first"]) for e in entries]
        y = [float(e["time_seconds"]) / 60 for e in entries]

        plt.scatter(x, y, color=color(genre_of[game]), label="WR")

        # log fit overlay: y = a * log(x+1) + b
        if len(x) >= 3:
            xarr = np.array(x)
            yarr = np.array(y)
            a, b = np.polyfit(np.log(xarr + 1), yarr, 1)
            x_fit = list(np.linspace(0, max(x), 120))
            y_fit = [a * np.log(xi + 1) + b for xi in x_fit]
            plt.plot(x_fit, y_fit, color="white", label="log fit")

        plt.title(f"Q2 Sättigungskurve: {game}  [{genre_of[game]}]  ({i}/{total})")
        plt.xlabel("Tage seit erstem WR")
        plt.ylabel("WR-Zeit (Minuten)")
        plt.plotsize(plt.terminal_width(), 28)
        show_and_wait(f"{i}/{total}")
