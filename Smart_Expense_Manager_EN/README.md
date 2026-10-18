# Smart Expense Manager — English Edition

> A personal finance Desktop application built with Python 3.10+  
> Architecture: OOP · 3-Layer · Pandas · Matplotlib · Tkinter

---

## Features

| # | Feature | Status |
|---|---------|--------|
| 1 | Add / Delete transactions (Income / Expense) | Done |
| 2 | Data validation (amount > 0, date format) | Done |
| 3 | Auto-calculated balance | Done |
| 4 | Category statistics | Done |
| 5 | Pie chart — expense breakdown | Done |
| 6 | Bar chart — monthly income vs expense | Done |
| 7 | Balance trend line chart | Done |
| 8 | **Correlation heatmap** (new) | Done |
| 9 | **KDE density distribution** (new) | Done |
| 10 | **Month / Year filter** on history & charts (new) | Done |
| 11 | Import from Excel (.xlsx / .xls) | Done |
| 12 | Import from CSV (auto-detects Vietnamese/English headers) | Done |
| 13 | Budget Alert with red progress bar | Done |
| 14 | Bulk delete (1 file write, no lag) | Done |
| 15 | Threaded import + delete with progress dialog | Done |
| 16 | Create new transaction file (with optional backup) | Done |

---

## Quick Start

```bash
# 1. Install dependencies
pip install pandas matplotlib openpyxl xlrd scipy

# 2. Run the app
python main.py
# or use the shortcut:
python run_en.py
```

---

## Project Structure

```
Smart_Expense_Manager_EN/
├── main.py                    ← Entry point
├── run_en.py                  ← Shortcut launcher
├── transactions.csv           ← Transaction data (auto-created)
├── budgets.json               ← Budget limits (auto-created)
├── sample_import.csv          ← Sample CSV for import testing
│
└── src/
    ├── models/
    │   └── transaction.py     ← Transaction ABC + Income/Expense + Factory
    ├── data/
    │   └── file_manager.py    ← CSV/Excel I/O with caching
    ├── business/
    │   ├── wallet.py          ← Facade: CRUD + bulk delete + import
    │   └── analyzer.py        ← Pandas analytics + period filter + KDE + correlation
    └── ui/
        └── app_gui.py         ← Tkinter GUI (4 tabs, persistent canvases)
```

---

## CSV Import Format

Standard headers (auto-detected):

```csv
Date,Category,Type,Amount,Note
2024-01-01,Salary,Income,20000000,January salary
2024-01-02,Food,Expense,150000,Lunch
```

Vietnamese headers are also supported:

| Standard | Vietnamese aliases |
|----------|-------------------|
| Date     | Ngày, Ngay, Transaction Date |
| Amount   | Số Tiền, So Tien, Tien |
| Type     | Loại, Loai, Trans Type |
| Category | Danh Mục, Danh Muc |
| Note     | Ghi Chú, Ghi Chu, Description |

---

## Charts Guide

| Chart | Description | Period Filter |
|-------|-------------|---------------|
| Bar Chart (Monthly) | Income vs Expense per month | Year |
| Correlation Heatmap | Pearson correlation between category daily totals | Year + Month |
| KDE Density | Distribution of transaction amounts with mean/median | Year + Month |

---

## Architecture

```
┌─────────────────────────────────────────┐
│   Presentation Layer  (src/ui/)         │
│   SmartExpenseApp  ←  Tkinter + MPL     │
└──────────────┬──────────────────────────┘
               │ calls public API
┌──────────────▼──────────────────────────┐
│   Business Layer   (src/business/)      │
│   Wallet (Facade)  ←→  FinancialAnalyzer│
└──────────────┬──────────────────────────┘
               │ reads / writes
┌──────────────▼──────────────────────────┐
│   Data Layer       (src/data/)          │
│   TransactionFileManager (CSV cache)    │
└─────────────────────────────────────────┘
```

### OOP Principles Applied

| Principle | Where |
|-----------|-------|
| **Abstraction** | `Transaction` is an ABC — cannot be instantiated directly |
| **Inheritance** | `IncomeTransaction`, `ExpenseTransaction` extend `Transaction` |
| **Polymorphism** | `get_signed_amount()` returns +/- depending on subclass |
| **Encapsulation** | `Wallet.__transactions` is private (name-mangled) |
| **Factory** | `TransactionFactory.create()` selects the correct subclass |
| **Facade** | `Wallet` hides FileManager + Analyzer complexity from UI |
| **Wrapper** | `FinancialAnalyzer` wraps DataFrame, exposes typed API |

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Multi-select rows | `Ctrl + Click` |

---

## Requirements

- Python 3.10+
- pandas ≥ 1.5
- matplotlib ≥ 3.5
- openpyxl (for .xlsx)
- xlrd (for .xls)
- scipy (for KDE density chart)

---

*Smart Expense Manager — English Edition*
