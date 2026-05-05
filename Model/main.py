"""
Speedrun Model — local LLM inference via Ollama.

Usage (from Model/ directory):
    python main.py

Prompts you to select a question, calls phi4-mini via Ollama (streaming),
and saves the structured JSON result to output/.

To add a new question: see questions/registry.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, KEEP_ALIVE, MODEL, OLLAMA_URL, OUTPUT_DIR
from questions.registry import QUESTION_REGISTRY


def main() -> None:
    print("\nSpeedrun Model — Lokale LLM-Inferenz")
    print("=" * 38)
    print(f"  Modell : {MODEL}")
    print(f"  Daten  : {DATA_DIR}")
    print(f"  Output : {OUTPUT_DIR}\n")

    if not QUESTION_REGISTRY:
        print("Keine Fragen registriert.")
        sys.exit(1)

    print("Verfügbare Fragen:")
    keys = list(QUESTION_REGISTRY)
    for k, meta in QUESTION_REGISTRY.items():
        print(f"  [{k}]  {meta['title']}  (Input: {meta['input']})")

    print()
    choice = input(f"Frage auswählen [{'/'.join(keys)}]:\n> ").strip().lower()

    if choice not in QUESTION_REGISTRY:
        print(f"Ungültige Auswahl: '{choice}'")
        sys.exit(1)

    meta = QUESTION_REGISTRY[choice]
    print(f"\n  Starte {meta['title']}")
    print("  " + "─" * 60)

    meta["fn"](
        data_dir   = DATA_DIR,
        output_dir = OUTPUT_DIR,
        model      = MODEL,
        ollama_url = OLLAMA_URL,
        keep_alive = KEEP_ALIVE,
    )


if __name__ == "__main__":
    main()
