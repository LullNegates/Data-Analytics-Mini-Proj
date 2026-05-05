from pathlib import Path

import plotext as plt

from charts.helpers import load_csv, show_and_wait


def graph_generic(path: Path) -> None:
    """Fallback for unrecognised CSVs — plots all numeric columns as lines."""
    rows = load_csv(path)
    if not rows:
        return

    numeric_cols = []
    for col in rows[0]:
        try:
            [float(r[col]) for r in rows if r[col]]
            numeric_cols.append(col)
        except ValueError:
            pass

    if not numeric_cols:
        print(f"  [skip] {path.name} — no numeric columns to plot")
        return

    for col in numeric_cols[:8]:
        vals = []
        for r in rows:
            try:
                vals.append(float(r[col]))
            except (ValueError, KeyError):
                vals.append(None)
        clean = [v for v in vals if v is not None]
        if clean:
            plt.plot(list(range(len(clean))), clean, label=col)

    plt.title(path.stem)
    plt.xlabel("Row index")
    plt.plotsize(plt.terminal_width(), 26)
    show_and_wait(path.stem)
