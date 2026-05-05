"""
Question registry — maps question IDs to their runner functions.

To add Q2 or Q3:
  1. Create questions/q2.py  with  def run_q2(data_dir, output_dir, model, ollama_url): ...
  2. Import it below and add one entry to QUESTION_REGISTRY.
  3. Done — main.py picks it up automatically.
"""

from questions.q1 import run_q1

QUESTION_REGISTRY: dict[str, dict] = {
    "q1": {
        "title": "Q1 — Prozentuale Zeitreduktion je Spielkategorie",
        "fn":    run_q1,
        "input": "q1_reduction.csv",
    },
    # ── add Q2 and Q3 below this line ──────────────────────────────────────
}
