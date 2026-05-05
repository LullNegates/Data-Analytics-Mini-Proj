"""
Dataset pipeline -- fetch, clean, then optionally run statistical analysis.

Usage:
    python main.py          # fetch + clean only
    python main.py --stats  # fetch + clean + full statistical analysis
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fetch import main as fetch
from clean import main as clean


def main() -> None:
    run_stats = "--stats" in sys.argv

    print("=== Step 1: Fetch ===")
    fetch()

    print("\n=== Step 2: Clean ===")
    clean()

    if run_stats:
        print("\n=== Step 3: Statistical Analysis ===")
        sys.path.insert(0, str(Path(__file__).parent / "analysis"))
        from analysis.run import main as run_analysis
        run_analysis()


if __name__ == "__main__":
    main()
