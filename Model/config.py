from pathlib import Path

OLLAMA_URL  = "http://localhost:11434/api/chat"
MODEL       = "phi4-mini"
KEEP_ALIVE  = 300  # seconds to keep model loaded after last response (0 = unload immediately)

# phi4-mini supports 128K context; Ollama defaults to 4096 without this setting.
NUM_CTX = 16384

DATA_DIR     = Path(__file__).parent.parent / "Dataset" / "data" / "clean"
ANALYSIS_DIR = Path(__file__).parent.parent / "Dataset" / "data" / "analysis"
DATASET_MD   = Path(__file__).parent.parent / "Dataset" / "Dataset.md"
OUTPUT_DIR   = Path(__file__).parent / "output"
