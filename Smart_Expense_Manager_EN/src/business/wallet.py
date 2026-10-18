"""
business/wallet.py
Business Layer: Wallet class managing transaction list.

Encapsulation: No direct access to internal transaction list
from outside — must go through add_transaction() and public methods.
"""

import pandas as pd
from typing import Optional

from src.models.transaction import Transaction, TransactionFactory
from src.data.file_manager import TransactionFileManager
from src.business.analyzer import FinancialAnalyzer


class Wallet:
    """
    Central class managing the expense wallet.

    Encapsulation:
    - __transactions is private (name-mangled with __)
    - All access through public methods
    - Business rules enforced at add_transaction()

    Facade Pattern:
    - Single entry point for the UI layer
    - Combines FileManager + Analyzer + Transaction models
    """

    def __init__(self, data_file: str = "transactions.csv"):
        self._file_manager = TransactionFileManager(data_file)
        self.__transactions: list[Transaction] = []
        self._budgets: dict = {}
        self._analyzer: Optional[FinancialAnalyzer] = None
        self._load()

    def _load(self) -> None:
        """Load data from file and rebuild analyzer (uses cache)."""
        self._budgets = self._file_manager.load_budgets()
        df = self._file_manager.load_data()
        self.__transactions = self._df_to_transactions(df)
        self._analyzer = FinancialAnalyzer(df)

    def _df_to_transactions(self, df: pd.DataFrame) -> list[Transaction]:
        result = []
        for _, row in df.iterrows():
            try:
                tx = TransactionFactory.create(
                    date=row["Date"],
                    category=str(row.get("Category", "")),
                    tx_type=str(row.get("Type", "")),
                    amount=float(row.get("Amount", 0)),
                    note=str(row.get("Note", "")),
                )
                result.append(tx)
            except (ValueError, KeyError):
                continue
        return result

    def _rebuild_analyzer(self) -> None:
        """Reload analyzer after each change (cache invalidated)."""
        df = self._file_manager.load_data(use_cache=False)
        self.__transactions = self._df_to_transactions(df)
        self._analyzer = FinancialAnalyzer(df)

    def add_transaction(self, date: str, category: str, tx_type: str,
                        amount: float, note: str = "") -> Transaction:
        """Add new transaction — single entry point (Encapsulation)."""
        tx = TransactionFactory.create(date, category, tx_type, amount, note)
        self._file_manager.save_transaction(tx)
        self.__transactions.insert(0, tx)
        self._rebuild_analyzer()
        return tx

    def delete_transaction(self, index: int) -> bool:
        success = self._file_manager.delete_transaction(index)
        if success:
            self._rebuild_analyzer()
        return success

    def delete_transactions_bulk(self, indices: list) -> tuple:
        """Delete multiple transactions at once: 1 read + 1 write."""
        df = self._file_manager.load_data(use_cache=False)
        valid = [i for i in indices if 0 <= i < len(df)]
        if not valid:
            return 0, len(indices)
        df_new = df.drop(index=valid).reset_index(drop=True)
        self._file_manager.save_all(df_new)
        self._rebuild_analyzer()
        return len(valid), len(indices) - len(valid)

    def delete_all_transactions(self) -> int:
        """Delete all transactions: 1 empty write + 1 rebuild."""
        count = self.get_transaction_count()
        empty = pd.DataFrame(columns=self._file_manager.COLUMNS)
        self._file_manager.save_all(empty)
        self._rebuild_analyzer()
        return count

    def get_all_transactions(self) -> list[Transaction]:
        return self.__transactions.copy()

    def get_transaction_count(self) -> int:
        return len(self.__transactions)

    def get_dataframe(self) -> pd.DataFrame:
        return self._file_manager.load_data()

    def get_analyzer(self) -> FinancialAnalyzer:
        if self._analyzer is None:
            self._rebuild_analyzer()
        return self._analyzer

    def filter_transactions(self,
                            year: Optional[int] = None,
                            month: Optional[int] = None,
                            tx_type: Optional[str] = None,
                            category: Optional[str] = None,
                            search: Optional[str] = None) -> pd.DataFrame:
        """Filter transactions using FinancialAnalyzer."""
        return self.get_analyzer().filter_data(
            year=year, month=month, tx_type=tx_type, category=category, search=search
        )

    def get_available_categories(self, tx_type: Optional[str] = None) -> list[str]:
        """Return available unique categories from data."""
        return self.get_analyzer().get_available_categories(tx_type)

    def reload(self) -> None:
        self._file_manager.invalidate_cache()
        self._load()

    def set_budget(self, category: str, limit: float) -> None:
        if limit < 0:
            raise ValueError("Budget limit cannot be negative")
        self._budgets[category] = limit
        self._file_manager.save_budgets(self._budgets)

    def get_budgets(self) -> dict:
        return self._budgets.copy()

    def get_budget_alerts(self, month: Optional[str] = None) -> list[dict]:
        return self.get_analyzer().check_budget_alerts(self._budgets, month)

    def import_from_excel(self, excel_path: str) -> int:
        """Import transactions from Excel file, returns row count."""
        df_new = self._file_manager.import_from_excel(excel_path)
        return self._merge_and_save(df_new)

    def import_from_csv(self, csv_path: str) -> int:
        """Import transactions from CSV bank statement."""
        df_new = self._file_manager.import_from_csv(csv_path)
        return self._merge_and_save(df_new)

    def _merge_and_save(self, df_new: pd.DataFrame) -> int:
        """Merge new DataFrame into existing data, deduplicate, save."""
        df_existing = self._file_manager.load_data()
        df_merged   = pd.concat([df_existing, df_new], ignore_index=True)
        df_merged   = df_merged.drop_duplicates(
            subset=["Date", "Category", "Amount"], keep="first"
        )
        self._file_manager.save_all(df_merged)
        self._rebuild_analyzer()
        return len(df_new)

    @property
    def balance(self) -> float:
        return self.get_analyzer().get_balance()

    @property
    def total_income(self) -> float:
        return self.get_analyzer().get_total_income()

    @property
    def total_expense(self) -> float:
        return self.get_analyzer().get_total_expense()

    def __repr__(self) -> str:
        return (f"Wallet(transactions={len(self.__transactions)}, "
                f"balance=${self.balance:,.2f})")
