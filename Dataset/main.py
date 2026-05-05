"""
Dataset pipeline -- fetch then clean.

Run: python main.py
"""

from fetch import main as fetch
from clean import main as clean


def main() -> None:
    print("=== Step 1: Fetch ===")
    fetch()
    print("\n=== Step 2: Clean ===")
    clean()


if __name__ == "__main__":
    main()
