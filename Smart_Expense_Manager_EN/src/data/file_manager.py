"""
data/file_manager.py
Data Layer: Handles CSV/JSON file I/O.
Uses pathlib for safe path handling.
"""

import pandas as pd
from pathlib import Path
from typing import Optional
import json
import shutil

from src.models.transaction import Transaction, TransactionFactory


class TransactionFileManager:
    """
    Manages reading/writing transaction data from CSV or Excel files.

    Attributes:
        _file_path (Path)   : Path to main data file.
        _budget_file (Path) : Path to budget JSON file.
        _df_cache           : In-memory DataFrame cache.
        COLUMNS (list)      : Required CSV columns.
    """

    COLUMNS     = ["Date", "Category", "Type", "Amount", "Note"]
    BUDGET_FILE = "budgets.json"

    _READ_DTYPES = {
        "Category": "str",
        "Type":     "str",
        "Amount":   "float64",
        "Note":     "str",
    }

    def __init__(self, file_path: str = "transactions.csv"):
        self._file_path   = Path(file_path)
        self._budget_file = self._file_path.parent / self.BUDGET_FILE
        self._df_cache: Optional[pd.DataFrame] = None
        self._ensure_file_exists()

    def invalidate_cache(self) -> None:
        """Clear cache when data changes."""
        self._df_cache = None

    def _ensure_file_exists(self) -> None:
        if not self._file_path.exists():
            pd.DataFrame(columns=self.COLUMNS).to_csv(
                self._file_path, index=False, encoding="utf-8-sig"
            )

    def _backup(self) -> None:
        if self._file_path.exists():
            shutil.copy2(self._file_path, self._file_path.with_suffix(".bak"))

    @staticmethod
    def _normalize_df(df: pd.DataFrame, columns: list) -> pd.DataFrame:
        """Normalize: ensure all columns exist, parse Date/Amount, drop NaT."""
        for col in columns:
            if col not in df.columns:
                df[col] = "" if col in ("Note", "Category") else 0
        df["Date"]   = pd.to_datetime(df["Date"],   format="mixed", errors="coerce")
        df["Amount"] = pd.to_numeric(df["Amount"],  errors="coerce").fillna(0)
        df = df.dropna(subset=["Date"])
        return df.sort_values("Date", ascending=False).reset_index(drop=True)

    def load_data(self, use_cache: bool = True) -> pd.DataFrame:
        """Load all transaction data from CSV file."""
        if use_cache and self._df_cache is not None:
            return self._df_cache.copy()
        if not self._file_path.exists() or self._file_path.stat().st_size == 0:
            return pd.DataFrame(columns=self.COLUMNS)
        df = pd.read_csv(
            self._file_path,
            dtype=self._READ_DTYPES,
            encoding="utf-8-sig",
            keep_default_na=False,
        )
        df = self._normalize_df(df, self.COLUMNS)
        self._df_cache = df
        return df.copy()

    def import_from_csv(self, csv_path: str) -> pd.DataFrame:
        """Import data from a CSV bank statement file with auto header detection."""
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {csv_path}")
        df = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)
        df.columns = [c.strip().title() for c in df.columns]
        column_mapping = {
            # Date
            "Transaction Date": "Date", "Date & Time": "Date", "Datetime": "Date",
            "Ngày": "Date", "Ngay": "Date", "Ngay Giao Dich": "Date",
            # Type
            "Trans Type": "Type", "Loại": "Type", "Loai": "Type", "Loai Giao Dich": "Type",
            # Amount
            "Số Tiền": "Amount", "So Tien": "Amount", "Tien": "Amount", "Giá Trị": "Amount",
            # Category
            "Danh Mục": "Category", "Danh Muc": "Category", "Phân Loại": "Category",
            # Note
            "Description": "Note", "Ghi Chú": "Note", "Ghi Chu": "Note", "Mô Tả": "Note",
        }
        df = df.rename(columns=column_mapping)
        # Normalize Type and Category if imported from Vietnamese source
        if "Type" in df.columns:
            type_map = {
                "thu nhập": "Income", "thu nhap": "Income", "thu": "Income", "income": "Income",
                "chi tiêu": "Expense", "chi tieu": "Expense", "chi": "Expense", "expense": "Expense",
            }
            df["Type"] = df["Type"].astype(str).apply(
                lambda s: type_map.get(s.strip().lower(), s.strip().title())
            )
        if "Category" in df.columns:
            cat_map = {
                "lương": "Salary", "luong": "Salary", "thưởng": "Bonus", "thuong": "Bonus",
                "lộc": "Bonus", "loc": "Bonus", "lộc / lì xì": "Bonus", "loc / li xi": "Bonus",
                "ăn uống": "Food", "an uong": "Food", "nhà cửa": "Rent", "nha cua": "Rent",
                "di chuyển": "Transport", "di chuyen": "Transport",
                "mua sắm": "Shopping", "mua sam": "Shopping", "học phí": "Education", "hoc phi": "Education",
                "y tế": "Healthcare", "y te": "Healthcare", "giải trí": "Entertainment", "giai tri": "Entertainment",
                "tiện ích": "Utilities", "tien ich": "Utilities", "đầu tư": "Investment", "dau tu": "Investment",
                "kinh doanh": "Business", "tiết kiệm": "Savings", "tiet kiem": "Savings", "khác": "Other Expense",
                "khac": "Other Expense"
            }
            df["Category"] = df["Category"].astype(str).apply(
                lambda s: cat_map.get(s.strip().lower(), s.strip().title())
            )
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").abs()
        df = self._normalize_df(df, self.COLUMNS)
        if df.empty:
            raise ValueError(
                "CSV file contains no valid data. "
                "Please check Date and Amount columns."
            )
        return df[self.COLUMNS]

    def import_from_excel(self, excel_path: str) -> pd.DataFrame:
        """Import data from an Excel bank statement file."""
        path = Path(excel_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {excel_path}")
        engine = "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"
        df = pd.read_excel(path, engine=engine, dtype=str)
        df.columns = [c.strip().title() for c in df.columns]
        column_mapping = {
            "Transaction Date": "Date", "Date & Time": "Date", "Datetime": "Date",
            "Ngày": "Date", "Ngay": "Date", "Ngay Giao Dich": "Date",
            "Trans Type": "Type", "Loại": "Type", "Loai": "Type",
            "Số Tiền": "Amount", "So Tien": "Amount", "Tien": "Amount",
            "Danh Mục": "Category", "Danh Muc": "Category",
            "Description": "Note", "Ghi Chú": "Note", "Ghi Chu": "Note",
        }
        df = df.rename(columns=column_mapping)
        if "Type" in df.columns:
            type_map = {
                "thu nhập": "Income", "thu nhap": "Income", "thu": "Income", "income": "Income",
                "chi tiêu": "Expense", "chi tieu": "Expense", "chi": "Expense", "expense": "Expense",
            }
            df["Type"] = df["Type"].astype(str).apply(
                lambda s: type_map.get(s.strip().lower(), s.strip().title())
            )
        for col in self.COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").abs()
        df = self._normalize_df(df, self.COLUMNS)
        return df[self.COLUMNS]

    def save_transaction(self, transaction: Transaction) -> None:
        self._backup()
        self.invalidate_cache()
        row = pd.DataFrame([transaction.to_dict()])
        row.to_csv(
            self._file_path,
            mode="a",
            header=not self._file_path.exists() or self._file_path.stat().st_size == 0,
            index=False,
            encoding="utf-8-sig",
        )

    def save_all(self, df: pd.DataFrame) -> None:
        self._backup()
        self.invalidate_cache()
        df.to_csv(self._file_path, index=False, encoding="utf-8-sig")

    def delete_transaction(self, index: int) -> bool:
        df = self.load_data(use_cache=False)
        if index < 0 or index >= len(df):
            return False
        df = df.drop(index=index).reset_index(drop=True)
        self.save_all(df)
        return True

    def load_budgets(self) -> dict:
        if not self._budget_file.exists():
            return {}
        try:
            with open(self._budget_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_budgets(self, budgets: dict) -> None:
        with open(self._budget_file, "w", encoding="utf-8") as f:
            json.dump(budgets, f, ensure_ascii=False, indent=2)

    @property
    def file_path(self) -> Path:
        return self._file_path
