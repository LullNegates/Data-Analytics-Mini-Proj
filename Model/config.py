from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "phi4-mini"

DATA_DIR   = Path(__file__).parent.parent / "Dataset" / "data" / "clean"
OUTPUT_DIR = Path(__file__).parent / "output"
