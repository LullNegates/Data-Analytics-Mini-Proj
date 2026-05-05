from pathlib import Path

OLLAMA_URL  = "http://localhost:11434/api/chat"
MODEL       = "phi4-mini"
KEEP_ALIVE  = 300  # seconds to keep model loaded after last response (0 = unload immediately)

DATA_DIR   = Path(__file__).parent.parent / "Dataset" / "data" / "clean"
OUTPUT_DIR = Path(__file__).parent / "output"
