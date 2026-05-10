from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"

# ── Single-model fallback (also used as the manager) ──────────────────────────
MODEL      = "phi4-mini"
KEEP_ALIVE = 300  # seconds Ollama keeps a model resident after last response

# phi4-mini supports 128K context; Ollama defaults to 4096 without this setting.
NUM_CTX = 16384

# ── Council of agents ─────────────────────────────────────────────────────────
# Three different small models from three different companies for maximum
# architectural diversity (MoA 2024: different base models outperform same-model
# personas because they surface different failure modes).
#
# Benchmark rationale (from Microsoft, Google, Meta, Alibaba model cards):
#   Statistician  qwen3:4b    Alibaba  MMLU ~70%, dual thinking/non-thinking mode,
#                                      best math/reasoning at 3-4B after phi4-mini
#   Domain Expert llama3.2:3b Meta     HellaSwag 77.2 = best commonsense in tier,
#                                      strongest world-knowledge for context interpretation
#   Skeptic       gemma3:4b   Google   Direct Gemma2 successor; GSM8K ~55 vs gemma2's
#                                      23.9 — gemma2 was too weak for quantitative critique
#
# Previous Skeptic (gemma2:2b): GSM8K 23.9%, MATH 15%, MMLU 51.3% — could not
# reliably identify statistical weaknesses. Replaced with gemma3:4b.
COUNCIL_MODELS: list[tuple[str, str]] = [
    # (persona_id, ollama_model_tag)
    # phi4-mini: GSM8K 88.6 %, MATH 64.0 %, BBH 70.4 % — strongest math in lineup
    ("statistician", "phi4-mini"),
    ("domain",       "llama3.2:3b"),
    ("skeptic",      "gemma3:4b"),
]

# qwen3:4b as Manager: reasoning model with visible thinking trace for synthesis.
# Runs with think=True so the CoT is printed to terminal during the synthesis step,
# giving an audit trail of which claims were trusted and why.
# phi4-mini has no thinking mode — qwen3 is the only model in the lineup that does.
MANAGER_MODEL = "qwen3:4b"

# Maximum number of fact-check → manager-revise cycles before we give up
# and write the draft with a fact_check_warnings field.
MAX_FACT_CHECK_REVISIONS = 2

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR     = Path(__file__).parent.parent / "Dataset" / "data" / "clean"
ANALYSIS_DIR = Path(__file__).parent.parent / "Dataset" / "data" / "analysis"
DATASET_MD   = Path(__file__).parent.parent / "Dataset" / "Dataset.md"
OUTPUT_DIR   = Path(__file__).parent / "output"

# Council outputs live alongside the single-agent outputs for easy diffing.
COUNCIL_OUTPUT_DIR = OUTPUT_DIR / "council"
