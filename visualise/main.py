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

# default data sources — CSV files and analysis JSON files
_DEFAULT_CLEAN    = Path(__file__).parent.parent / "Dataset" / "data" / "clean"
_DEFAULT_ANALYSIS = Path(__file__).parent.parent / "Dataset" / "data" / "analysis"
_DEFAULT_DATA     = _DEFAULT_CLEAN  # kept for backwards compat


def resolve_paths(raw_inputs: list[str]) -> list[Path]:
    paths = []
    for raw in raw_inputs:
        p = Path(raw.strip())
        if p.exists():
            paths.append(p)
            continue
        # Try clean/ directory (CSV files)
        candidate = _DEFAULT_CLEAN / raw.strip()
        if candidate.exists():
            paths.append(candidate)
            continue
        # Try analysis/ directory (JSON files, e.g. "q3_stats" or "q3_stats.json")
        name = raw.strip()
        if not name.endswith(".json"):
            name += ".json"
        candidate = _DEFAULT_ANALYSIS / name
        if candidate.exists():
            paths.append(candidate)
            continue
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
        folder_raw = input(f"Folder path [Enter = default clean/], 'analysis' for JSON charts:\n> ").strip()
        if folder_raw.lower() == "analysis":
            folder = _DEFAULT_ANALYSIS
        else:
            folder = Path(folder_raw) if folder_raw else _DEFAULT_CLEAN
        if not folder.is_dir():
            print(f"Not a directory: {folder}")
            sys.exit(1)
        paths = sorted(folder.glob("*.csv")) + sorted(folder.glob("*.json"))
        if not paths:
            print("No data files found.")
            sys.exit(1)
        print(f"\nFound {len(paths)} file(s) in {folder.name}/:")
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
