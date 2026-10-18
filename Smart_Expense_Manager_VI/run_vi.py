#!/usr/bin/env python3
"""
run_vi.py — Phiên bản Tiếng Việt launcher shortcut.

Cách dùng:
    python run_vi.py                   # dùng transactions.csv mặc định
    python run_vi.py tai_chinh.csv     # dùng file dữ liệu tùy chọn
"""
import sys
from pathlib import Path

# Đảm bảo stdout/stderr nhận tiếng Việt trên mọi nền tảng (Windows, Linux, macOS)
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.ui.app_gui import main

if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else "transactions.csv"
    main(data_file)
