"""
Speedrun Data Visualiser — terminal-based, no GUI window.

Usage:
    python main.py

Prompts for CSV files (comma-separated names or paths) or 'all' to walk a folder.
File names without a path are resolved against Dataset/data/clean/ automatically.

To add a new chart type: see charts/registry.py.
"""

import sys
from pathlib import Path

# ensure charts/ is importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

from charts.registry import CHART_REGISTRY, FALLBACK

# default data source — adjust if Dataset/ moves
_DEFAULT_DATA = Path(__file__).parent.parent / "Dataset" / "data" / "clean"


def resolve_paths(raw_inputs: list[str]) -> list[Path]:
    paths = []
    for raw in raw_inputs:
        p = Path(raw.strip())
        if not p.exists():
            p = _DEFAULT_DATA / raw.strip()
        if p.exists():
            paths.append(p)
        else:
            print(f"  [warn] not found: {raw.strip()}")
    return paths


def plot_file(path: Path) -> None:
    fn = CHART_REGISTRY.get(path.stem, FALLBACK)
    print(f"\n  {path.name}  →  {fn.__name__}\n")
    try:
        fn(path)
    except KeyboardInterrupt:
        print("\n  Skipped.")
    except Exception as exc:
        print(f"  [error] {exc}")


def main() -> None:
    print("\nSpeedrun Data Visualiser")
    print("=" * 30)
    print(f"Default data folder: {_DEFAULT_DATA}\n")

    user_input = input("CSV files (comma-separated) or 'all' for a folder:\n> ").strip()

    if user_input.lower() == "all":
        folder_raw = input(f"Folder path [Enter = default]:\n> ").strip()
        folder = Path(folder_raw) if folder_raw else _DEFAULT_DATA
        if not folder.is_dir():
            print(f"Not a directory: {folder}")
            sys.exit(1)
        paths = sorted(folder.glob("*.csv"))
        if not paths:
            print("No CSV files found.")
            sys.exit(1)
        print(f"\nFound {len(paths)} CSV file(s) in {folder.name}/:")
        for p in paths:
            tag = " *" if p.stem in CHART_REGISTRY else ""
            print(f"  {p.name}{tag}")
        print("  (* = purpose-built chart)\n")
        input("Press Enter to start...")
    else:
        parts = [p for p in user_input.split(",") if p.strip()]
        paths = resolve_paths(parts)

    if not paths:
        print("No valid files to plot.")
        sys.exit(1)

    for path in paths:
        plot_file(path)

    print("\nAll charts done.")


if __name__ == "__main__":
    main()
