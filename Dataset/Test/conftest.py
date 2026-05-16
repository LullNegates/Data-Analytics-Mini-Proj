"""
Shared pytest configuration: adds analysis/ to sys.path so all test modules can
import from it without installing a package.
"""
import sys
from pathlib import Path

# analysis/ lives one level up from this Test/ folder
sys.path.insert(0, str(Path(__file__).parent.parent / "analysis"))
