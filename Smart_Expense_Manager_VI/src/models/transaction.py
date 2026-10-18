# -*- coding: utf-8 -*-
"""
models/transaction.py
Tầng Model: Định nghĩa các lớp giao dịch với đầy đủ tính OOP.
- Abstract class Transaction (tính trừu tượng)
- IncomeTransaction và ExpenseTransaction (tính kế thừa & đa hình)
"""

from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass, field


class Transaction(ABC):
    """
    Lớp trừu tượng cơ sở cho mọi loại giao dịch tài chính.
    Áp dụng: Tính trừu tượng (Abstraction) và Tính đóng gói (Encapsulation).
    """

    VALID_CATEGORIES = {
        "Income": ["Lương", "Thưởng", "Lộc / Lì xì", "Đầu tư", "Kinh doanh", "Tiết kiệm", "Thu nhập khác"],
        "Expense": ["Ăn uống", "Nhà cửa", "Di chuyển", "Mua sắm", "Học phí", "Y tế", "Giải trí", "Tiện ích", "Khác"]
    }

    def __init__(self, date: str, category: str, amount: float, note: str = ""):
        self._date = self._validate_date(date)
        self._category = category
        self._amount = self._validate_amount(amount)
        self._note = note
        self._created_at = datetime.now()

    # ── Validation ────────────────────────────────────────────────
    @staticmethod
    def _validate_date(date_str: str) -> datetime:
        """Kiểm tra và parse ngày giờ. Chấp nhận DD/MM/YYYY, YYYY-MM-DD có hoặc không có giờ."""
        if isinstance(date_str, datetime):
            return date_str
        cleaned = str(date_str).strip()
        for fmt in (
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
        ):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            pass
        raise ValueError(f"Ngày không hợp lệ: '{date_str}'. Dùng định dạng DD/MM/YYYY hoặc YYYY-MM-DD (có thể kèm giờ:phút)")

    @staticmethod
    def _validate_amount(amount) -> float:
        """Kiểm tra số tiền phải > 0."""
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            raise ValueError(f"Số tiền không hợp lệ: '{amount}'")
        if amount <= 0:
            raise ValueError(f"Số tiền phải lớn hơn 0, nhận được: {amount}")
        return amount

    # ── Abstract method (Tính đa hình) ────────────────────────────
    @abstractmethod
    def get_signed_amount(self) -> float:
        """Trả về số tiền có dấu: +Income / -Expense (đa hình)."""
        pass

    @abstractmethod
    def get_type(self) -> str:
        """Trả về loại giao dịch dạng chuỗi."""
        pass

    @abstractmethod
    def get_type_label(self) -> str:
        """Trả về nhãn hiển thị tiếng Việt."""
        pass

    # ── Properties (Encapsulation) ─────────────────────────────────
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

    # ── Representation ─────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Chuyển đổi sang dict để ghi file CSV."""
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
        date_str = self._date.strftime("%d/%m/%Y %H:%M") if has_time else self._date.strftime("%d/%m/%Y")
        return (f"{self.__class__.__name__}("
                f"date={date_str}, "
                f"category='{self._category}', "
                f"amount={self._amount:,.0f} ₫)")

    def __eq__(self, other) -> bool:
        if not isinstance(other, Transaction):
            return False
        return (self._date == other._date and
                self._category == other._category and
                self._amount == other._amount)


class IncomeTransaction(Transaction):
    """
    Giao dịch Thu nhập.
    Kế thừa từ Transaction, get_signed_amount() trả về giá trị DƯƠNG (+).
    """

    def get_signed_amount(self) -> float:
        """Thu nhập: cộng vào số dư (+)."""
        return +self._amount

    def get_type(self) -> str:
        return "Income"

    def get_type_label(self) -> str:
        return "Thu nhập"


class ExpenseTransaction(Transaction):
    """
    Giao dịch Chi tiêu.
    Kế thừa từ Transaction, get_signed_amount() trả về giá trị ÂM (-).
    """

    def get_signed_amount(self) -> float:
        """Chi tiêu: trừ vào số dư (-)."""
        return -self._amount

    def get_type(self) -> str:
        return "Expense"

    def get_type_label(self) -> str:
        return "Chi tiêu"


class TransactionFactory:
    """
    Factory Pattern: Tạo đúng loại Transaction từ dữ liệu thô.
    Tập trung logic khởi tạo, UI không cần biết cách tạo object.
    """

    @staticmethod
    def create(date: str, category: str, tx_type: str,
               amount: float, note: str = "") -> Transaction:
        """
        Tạo IncomeTransaction hoặc ExpenseTransaction tùy theo tx_type.

        Args:
            date: Ngày giao dịch (YYYY-MM-DD hoặc DD/MM/YYYY)
            category: Danh mục
            tx_type: "Income"/"Thu nhập" hoặc "Expense"/"Chi tiêu"
            amount: Số tiền (> 0)
            note: Ghi chú

        Returns:
            Transaction object tương ứng

        Raises:
            ValueError: Nếu tx_type không hợp lệ
        """
        tx_type_str = str(tx_type).strip()
        tx_lower = tx_type_str.lower()
        if tx_lower in ("income", "thu nhập", "thu"):
            return IncomeTransaction(date, category, amount, note)
        elif tx_lower in ("expense", "chi tiêu", "chi"):
            return ExpenseTransaction(date, category, amount, note)
        else:
            raise ValueError(f"Loại giao dịch không hợp lệ: '{tx_type}'. "
                             f"Chỉ chấp nhận 'Income'/'Thu nhập' hoặc 'Expense'/'Chi tiêu'.")
