#!/usr/bin/env python3
"""
run_en.py — English Edition launcher shortcut.

Usage:
    python run_en.py                  # uses transactions.csv
    python run_en.py my_finance.csv   # custom data file
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.ui.app_gui import main

if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else "transactions.csv"
    main(data_file)
