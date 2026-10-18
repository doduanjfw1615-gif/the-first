"""
main.py — Application entry point.
Adds the project root to sys.path and launches the GUI.
"""
import sys
import io
from pathlib import Path

# Đảm bảo stdout/stderr nhận tiếng Việt trên mọi nền tảng (Windows, Linux, macOS)
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.ui.app_gui import main

if __name__ == "__main__":
    data_file = str(ROOT / "transactions.csv")
    main(data_file)
