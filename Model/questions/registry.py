"""
Question registry — maps question IDs to their runner functions.

To add a new question:
  1. Create questions/qN.py with def run_qN(data_dir, output_dir, analysis_dir,
     dataset_md, model, ollama_url, keep_alive, num_ctx): ...
  2. Import and register it below.
"""

from questions.q1 import run_q1
from questions.q2 import run_q2
from questions.q3 import run_q3

QUESTION_REGISTRY: dict[str, dict] = {
    "q1": {
        "title": "Q1 — Prozentuale Zeitreduktion je Spielkategorie",
        "fn":    run_q1,
        "input": "q1_reduction.csv + q1_stats.json",
    },
    "q2": {
        "title": "Q2 — Sättigungsanalyse (AIC-Kurvenanpassung + Strukturbruch)",
        "fn":    run_q2,
        "input": "q2_saturation.csv (aggregiert) + q2_stats.json",
    },
    "q3": {
        "title": "Q3 — WR-Lebensdauer (Kaplan-Meier Überlebensanalyse)",
        "fn":    run_q3,
        "input": "q3_lifetimes.csv (aggregiert) + q3_stats.json",
    },
}
