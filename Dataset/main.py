"""
Dataset pipeline -- fetch, clean, then optionally run statistical analysis.

Usage:
    python main.py              # fetch + clean only
    python main.py --stats      # fetch + clean + full statistical analysis
    python main.py --tas        # also fetch TAS timelines from TASVideos.org
    python main.py --stats --tas  # all steps
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fetch import main as fetch
from clean import main as clean


def main() -> None:
    run_stats = "--stats" in sys.argv
    run_tas = "--tas" in sys.argv

    print("=== Step 1: Fetch (speedrun.com) ===")
    fetch()

    print("\n=== Step 2: Clean ===")
    clean()

    if run_tas:
        print("\n=== Step 3: Fetch TAS Timelines (TASVideos.org) ===")
        from fetch_tas import main as fetch_tas
        fetch_tas()

    if run_stats:
        step = 4 if run_tas else 3
        print(f"\n=== Step {step}: Statistical Analysis ===")
        sys.path.insert(0, str(Path(__file__).parent / "analysis"))
        from analysis.run import main as run_analysis
        run_analysis()


if __name__ == "__main__":
    main()
