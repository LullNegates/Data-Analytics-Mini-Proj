"""Shared utilities used by every chart module."""

import csv
from datetime import datetime
from pathlib import Path

import plotext as plt

# One colour per genre — passed as plotext colour names
GENRE_COLORS = {
    "Platformer":       "blue",
    "Action-Adventure": "green",
    "RPG":              "magenta",
    "FPS":              "red",
    "Puzzle":           "orange",
    "Sandbox":          "cyan",
    "Arcade":           "yellow",
}
_DEFAULT_COLOR = "white"


def color(genre: str) -> str:
    return GENRE_COLORS.get(genre, _DEFAULT_COLOR)


def load_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_date(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def show_and_wait(label: str = "") -> None:
    """Render current plotext figure to terminal then wait for Enter."""
    plt.show()
    plt.clear_figure()
    prompt = f"  [{label}] " if label else "  "
    input(f"{prompt}Press Enter for next chart...")
    print()
