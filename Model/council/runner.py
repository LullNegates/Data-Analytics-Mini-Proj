"""Interactive entry point for the council.

Invoked by ``Model/main.py``. Asks which question to run (q1/q2/q3/all),
then dispatches to ``orchestrator.run_council``.
"""

from __future__ import annotations

import sys

from config import (ANALYSIS_DIR, COUNCIL_MODELS, COUNCIL_OUTPUT_DIR, DATA_DIR,
                    DATASET_MD, KEEP_ALIVE, MANAGER_MODEL,
                    MAX_FACT_CHECK_REVISIONS, NUM_CTX, OLLAMA_URL, OUTPUT_DIR)
from council.orchestrator import QUESTION_TITLES, run_council


def _menu() -> str:
    print("\nVerfügbare Fragen:")
    for q, title in QUESTION_TITLES.items():
        print(f"  [{q}]  {title}")
    print(f"  [all] alle drei nacheinander")
    return input("Frage auswählen [q1/q2/q3/all]:\n> ").strip().lower()


def main(question: str | None = None) -> None:
    if question is None:
        question = _menu()

    if question == "all":
        questions = ["q1", "q2", "q3"]
    elif question in QUESTION_TITLES:
        questions = [question]
    else:
        print(f"Ungültige Auswahl: '{question}'")
        sys.exit(1)

    for q in questions:
        run_council(
            question           = q,
            council_models     = COUNCIL_MODELS,
            manager_model      = MANAGER_MODEL,
            data_dir           = DATA_DIR,
            analysis_dir       = ANALYSIS_DIR,
            dataset_md         = DATASET_MD,
            output_dir         = OUTPUT_DIR,
            council_output_dir = COUNCIL_OUTPUT_DIR,
            ollama_url         = OLLAMA_URL,
            keep_alive         = KEEP_ALIVE,
            num_ctx            = NUM_CTX,
            max_revisions      = MAX_FACT_CHECK_REVISIONS,
        )


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg)
