"""
models/transaction.py
Model Layer: Transaction classes with full OOP design.
- Abstract class Transaction (Abstraction)
- IncomeTransaction and ExpenseTransaction (Inheritance & Polymorphism)
"""

from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass, field


class Transaction(ABC):
    """
    Abstract base class for all financial transactions.
    Applies: Abstraction and Encapsulation.
    """

    VALID_CATEGORIES = {
        "Income": ["Salary", "Bonus", "Savings", "Investment", "Business", "Other Income"],
        "Expense": ["Food", "Rent", "Transport", "Entertainment",
                    "Healthcare", "Education", "Utilities", "Shopping", "Other Expense"]
    }

    def __init__(self, date: str, category: str, amount: float, note: str = ""):
        self._date = self._validate_date(date)
        self._category = category
        self._amount = self._validate_amount(amount)
        self._note = note
        self._created_at = datetime.now()

    @staticmethod
    def _validate_date(date_str: str) -> datetime:
        """Validate and parse date/datetime string. Raises ValueError on bad format."""
        if isinstance(date_str, datetime):
            return date_str
        cleaned = str(date_str).strip()
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%d-%m-%Y",
        ):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            pass
        raise ValueError(f"Invalid date: '{date_str}'. Use format YYYY-MM-DD or YYYY-MM-DD HH:MM")

    @staticmethod
    def _validate_amount(amount) -> float:
        """Validate amount must be > 0."""
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid amount: '{amount}'")
        if amount <= 0:
            raise ValueError(f"Amount must be greater than 0, got: {amount}")
        return amount

    @abstractmethod
    def get_signed_amount(self) -> float:
        """Return signed amount: +Income / -Expense (polymorphism)."""
        pass

    @abstractmethod
    def get_type(self) -> str:
        """Return transaction type as string."""
        pass

    @abstractmethod
    def get_type_label(self) -> str:
        """Return display label."""
        pass

    @property
    def date(self) -> datetime:
        return self._date

    @property
    def category(self) -> str:
        return self._category

    @property
    def amount(self) -> float:
        return self._amount

    @property
    def note(self) -> str:
        return self._note

    @note.setter
    def note(self, value: str):
        self._note = str(value)

    def to_dict(self) -> dict:
        """Convert to dict for CSV writing."""
        has_time = self._date.hour != 0 or self._date.minute != 0 or self._date.second != 0
        date_str = self._date.strftime("%Y-%m-%d %H:%M") if has_time else self._date.strftime("%Y-%m-%d")
        return {
            "Date": date_str,
            "Category": self._category,
            "Type": self.get_type(),
            "Amount": self._amount,
            "Note": self._note,
        }

    def __repr__(self) -> str:
        has_time = self._date.hour != 0 or self._date.minute != 0 or self._date.second != 0
        date_str = self._date.strftime("%Y-%m-%d %H:%M") if has_time else self._date.strftime("%Y-%m-%d")
        return (f"{self.__class__.__name__}("
                f"date={date_str}, "
                f"category='{self._category}', "
                f"amount=${self._amount:,.2f})")

    def __eq__(self, other) -> bool:
        if not isinstance(other, Transaction):
            return False
        return (self._date == other._date and
                self._category == other._category and
                self._amount == other._amount)


class IncomeTransaction(Transaction):
    """Income transaction. get_signed_amount() returns POSITIVE (+)."""

    def get_signed_amount(self) -> float:
        return +self._amount

    def get_type(self) -> str:
        return "Income"

    def get_type_label(self) -> str:
        return "Income"


class ExpenseTransaction(Transaction):
    """Expense transaction. get_signed_amount() returns NEGATIVE (-)."""

    def get_signed_amount(self) -> float:
        return -self._amount

    def get_type(self) -> str:
        return "Expense"

    def get_type_label(self) -> str:
        return "Expense"


class TransactionFactory:
    """Factory Pattern: Create correct Transaction type from raw data."""

    @staticmethod
    def create(date: str, category: str, tx_type: str,
               amount: float, note: str = "") -> Transaction:
        tx_type_str = str(tx_type).strip()
        tx_lower = tx_type_str.lower()
        if tx_lower in ("income", "thu nhập", "thu"):
            return IncomeTransaction(date, category, amount, note)
        elif tx_lower in ("expense", "chi tiêu", "chi"):
            return ExpenseTransaction(date, category, amount, note)
        else:
            raise ValueError(f"Invalid transaction type: '{tx_type}'. "
                             f"Only 'Income' or 'Expense' accepted.")
