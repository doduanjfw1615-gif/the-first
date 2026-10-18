# the-first
Hi, it just my idea about manage the personal finance, hope u enjoy this
# Smart Expense Manager — English & Vietnamese Editions

> Personal finance desktop application — Python 3.10+
> Architecture: OOP · 3-layer · Pandas · Matplotlib · Tkinter

This repository contains **2 versions of the same application**: an **English** UI and a **Vietnamese** UI. Each version is a standalone folder that runs independently with its own data.

---

## Versions

| Folder | UI Language | Quick launch file |
|---------|-------------------|-----------------|
| `Smart_Expense_Manager_EN/` | English | `SmartExpenseManager_EN.exe` |
| `Smart_Expense_Manager_VI/` | Vietnamese | `SmartExpenseManager_VI.exe` |

See the `README.md` inside each subfolder for details on features, architecture, and CSV import format.

---

## Common Features

- Add / delete Income / Expense transactions with automatic balance calculation
- Category statistics and budget alerts with a red progress bar
- Charts: pie (spending breakdown), bar (monthly income/expenses), line (balance trend), **correlation heatmap**, **KDE density**
- Filter history & charts by month / year
- CSV import (auto-detects Vietnamese/English column names) and Excel (.xlsx / .xls)
- Multi-row deletion; import/delete run in a separate thread with a progress bar
- Create a new data file (with optional backup)

---

## How to Run

### Option 1 — Double-click the exe file (no installation needed)

```
Smart_Expense_Manager_EN\SmartExpenseManager_EN.exe
Smart_Expense_Manager_VI\SmartExpenseManager_VI.exe
```

Notes:

- **Keep the exe inside the project folder** (next to `transactions.csv`) — the app reads/writes data at that location.
- The first launch is a few seconds slower (the `--onefile` build extracts to a temp directory); Windows SmartScreen may show a warning → choose **More info → Run anyway**.
- Each exe is ~283MB because it bundles Python + pandas + numpy + matplotlib.

### Option 2 — Run with Python (for development / code changes)

```bash
# Enter the folder of the version you want to run, e.g. the EN version:
cd Smart_Expense_Manager_EN

# Install dependencies (first time)
pip install pandas matplotlib openpyxl xlrd scipy

# Run the app
python main.py
# or shortcut:
python run_en.py        # VI version: python run_vi.py
```

---

## Overall Structure

```
the-first-main/
├── README.md                          ← This file (overview)
│
├── Smart_Expense_Manager_EN/          ← English version
│   ├── SmartExpenseManager_EN.exe     ← Double-click to open the app
│   ├── main.py                        ← Launch point
│   ├── run_en.py                      ← Shortcut launcher
│   ├── transactions.csv               ← Transaction data
│   ├── budgets.json                   ← Budget limits
│   └── src/                           ← models / data / business / ui
│
└── Smart_Expense_Manager_VI/          ← Vietnamese version (similar structure)
    ├── SmartExpenseManager_VI.exe
    ├── main.py
    ├── run_vi.py
    ├── transactions.csv
    ├── budgets.json
    └── src/
```

---

## Requirements (when running with Python)

- Python 3.10 or later
- pandas ≥ 1.5 · matplotlib ≥ 3.5 · numpy
- openpyxl (for .xlsx) · xlrd (for .xls) · scipy (for KDE charts)

No installation is needed when running the exe.

---

## Rebuilding the exe (after code changes)

```bash
cd Smart_Expense_Manager_EN
python -m PyInstaller --onefile --noconsole --name SmartExpenseManager_EN run_en.py

cd Smart_Expense_Manager_VI
python -m PyInstaller --onefile --noconsole --name SmartExpenseManager_VI run_vi.py
```

The new exe is located in the `dist\` folder of each directory — copy it to the project root (next to `transactions.csv`), then delete `build/`, `dist/`, and `*.spec`.

---

*Smart Expense Manager — English Edition & Vietnamese Version*
