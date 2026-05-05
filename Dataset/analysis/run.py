"""
Run all three statistical analyses and print a combined summary.

Usage (from Dataset/ directory):
    python analysis/run.py
"""

import sys
from pathlib import Path

# Allow importing sibling analysis modules when run directly
sys.path.insert(0, str(Path(__file__).parent))

import q1_analysis
import q2_analysis
import q3_analysis


def main() -> None:
    print("\nSpeedrun Statistical Analysis")
    print("=" * 50)
    print("Reads from data/clean/  |  Writes to data/analysis/\n")

    errors = []

    print("[Q1] Percentage reduction + genre comparison...")
    try:
        r1 = q1_analysis.run()
        q1_analysis.print_summary(r1)
    except Exception as exc:
        print(f"  [error] {exc}")
        errors.append(f"Q1: {exc}")

    print("\n[Q2] Saturation model comparison...")
    try:
        r2 = q2_analysis.run()
        q2_analysis.print_summary(r2)
    except Exception as exc:
        print(f"  [error] {exc}")
        errors.append(f"Q2: {exc}")

    print("\n[Q3] WR lifetime distribution...")
    try:
        r3 = q3_analysis.run()
        q3_analysis.print_summary(r3)
    except Exception as exc:
        print(f"  [error] {exc}")
        errors.append(f"Q3: {exc}")

    print("\n" + "=" * 50)
    if errors:
        print(f"Completed with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("All analyses complete. Results in Dataset/data/analysis/")


if __name__ == "__main__":
    main()
