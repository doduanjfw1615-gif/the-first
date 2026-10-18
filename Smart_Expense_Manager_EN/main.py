"""
main.py — Application entry point.
Adds the project root to sys.path and launches the GUI.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.ui.app_gui import main

if __name__ == "__main__":
    data_file = str(ROOT / "transactions.csv")
    main(data_file)
