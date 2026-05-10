"""
Speedrun Model — local LLM inference via the Council of Agents.

Usage (from Model/ directory):
    python main.py            # interactive Q1/Q2/Q3 picker
    python main.py q1         # run a specific question
    python main.py all        # run all three sequentially

The single-agent runners (questions/q*.py) have been replaced by the
council in Model/council/. See docs/council-architecture.md for design.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import (ANALYSIS_DIR, COUNCIL_MODELS, COUNCIL_OUTPUT_DIR, DATA_DIR,
                    MANAGER_MODEL, NUM_CTX, OUTPUT_DIR)
from council import runner


def main() -> None:
    print("\nSpeedrun Model — Council of Agents")
    print("=" * 38)
    print(f"  Council : {', '.join(f'{p}/{m}' for p, m in COUNCIL_MODELS)}")
    print(f"  Manager : {MANAGER_MODEL}")
    print(f"  num_ctx : {NUM_CTX:,} Tokens")
    print(f"  Daten   : {DATA_DIR}")
    print(f"  Analyse : {ANALYSIS_DIR}")
    print(f"  Output  : {COUNCIL_OUTPUT_DIR}")
    print(f"  Baseline: {OUTPUT_DIR}  (single-agent JSONs für Vergleich)")
    print()

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    runner.main(arg)


if __name__ == "__main__":
    main()
