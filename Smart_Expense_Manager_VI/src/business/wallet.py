# -*- coding: utf-8 -*-
"""
business/wallet.py
Tầng Nghiệp vụ: Lớp Wallet quản lý danh sách giao dịch.

Tính đóng gói: Không cho phép truy cập trực tiếp list giao dịch
từ bên ngoài — phải qua add_transaction() và các phương thức công khai.

CẢI TIẾN (v2):
  - import_from_csv(): Thêm support import CSV (gọi qua FileManager)
  - _load() dùng cache của FileManager → khởi động nhanh hơn
  - _rebuild_analyzer() không đọc lại disk nếu cache còn hiệu lực
"""

import pandas as pd
from typing import Optional

from src.models.transaction import Transaction, TransactionFactory
from src.data.file_manager import TransactionFileManager
from src.business.analyzer import FinancialAnalyzer


class Wallet:
    """
    Lớp trung tâm quản lý Ví tiền.

    Tính đóng gói (Encapsulation):
    - __transactions là private (name-mangled với __)
    - Mọi truy cập đều qua phương thức công khai
    - Business rules được thực thi tại add_transaction()

    Facade Pattern:
    - Là điểm vào duy nhất cho tầng UI
    - Kết hợp FileManager + Analyzer + Transaction models
    """

    def __init__(self, data_file: str = "transactions.csv"):
        self._file_manager = TransactionFileManager(data_file)
        self.__transactions: list[Transaction] = []
        self._budgets: dict = {}
        self._analyzer: Optional[FinancialAnalyzer] = None
        self._load()

    # ── Internal loading ──────────────────────────────────────────

    def _load(self) -> None:
        """Tải dữ liệu từ file và rebuild analyzer (dùng cache)."""
        self._budgets = self._file_manager.load_budgets()
        df = self._file_manager.load_data()          # dùng cache nếu có
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
        """Tải lại analyzer sau mỗi thay đổi (cache đã bị invalidate)."""
        df = self._file_manager.load_data(use_cache=False)
        self.__transactions = self._df_to_transactions(df)
        self._analyzer = FinancialAnalyzer(df)

    # ── Transaction CRUD ──────────────────────────────────────────

    def add_transaction(self, date: str, category: str, tx_type: str,
                        amount: float, note: str = "") -> Transaction:
        """
        Thêm giao dịch mới — điểm vào duy nhất (Encapsulation).
        Validate → Tạo object → Ghi file → Rebuild analyzer
        """
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
        """
        Xóa nhiều giao dịch CÙNG LÚC: chỉ 1 lần đọc + 1 lần ghi file.
        Nhanh hơn gọi delete_transaction() N lần khi N lớn.

        Args:
            indices: list[int] — chỉ số cần xóa (thứ tự bất kỳ).

        Returns:
            (deleted_count, failed_count)
        """
        df = self._file_manager.load_data(use_cache=False)
        valid = [i for i in indices if 0 <= i < len(df)]
        if not valid:
            return 0, len(indices)

        df_new = df.drop(index=valid).reset_index(drop=True)
        self._file_manager.save_all(df_new)   # 1 lần ghi duy nhất
        self._rebuild_analyzer()               # 1 lần rebuild duy nhất
        return len(valid), len(indices) - len(valid)

    def delete_all_transactions(self) -> int:
        """
        Xóa toàn bộ giao dịch: 1 lần ghi file rỗng + 1 rebuild.
        Nhanh hơn nhiều so với xóa từng cái một.

        Returns:
            Số giao dịch đã xóa.
        """
        import pandas as pd
        count = self.get_transaction_count()
        empty = pd.DataFrame(columns=self._file_manager.COLUMNS)
        self._file_manager.save_all(empty)
        self._rebuild_analyzer()
        return count

    def get_all_transactions(self) -> list[Transaction]:
        return self.__transactions.copy()

    def get_transaction_count(self) -> int:
        return len(self.__transactions)

    # ── Data access ───────────────────────────────────────────────

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
        """Lọc giao dịch sử dụng FinancialAnalyzer."""
        return self.get_analyzer().filter_data(
            year=year, month=month, tx_type=tx_type, category=category, search=search
        )

    def get_available_categories(self, tx_type: Optional[str] = None) -> list[str]:
        """Trả về danh sách danh mục có trong dữ liệu."""
        return self.get_analyzer().get_available_categories(tx_type)

    def reload(self) -> None:
        self._file_manager.invalidate_cache()
        self._load()

    # ── Budget management ─────────────────────────────────────────

    def set_budget(self, category: str, limit: float) -> None:
        if limit < 0:
            raise ValueError("Hạn mức ngân sách không được âm")
        self._budgets[category] = limit
        self._file_manager.save_budgets(self._budgets)

    def get_budgets(self) -> dict:
        return self._budgets.copy()

    def get_budget_alerts(self, month: Optional[str] = None) -> list[dict]:
        return self.get_analyzer().check_budget_alerts(self._budgets, month)

    # ── Import ────────────────────────────────────────────────────

    def import_from_excel(self, excel_path: str) -> int:
        """Import giao dịch từ file Excel, trả về số dòng đã import."""
        df_new = self._file_manager.import_from_excel(excel_path)
        return self._merge_and_save(df_new)

    def import_from_csv(self, csv_path: str) -> int:
        """
        [CHỨC NĂNG MỚI] Import giao dịch từ file CSV sao kê ngân hàng.

        Tự động loại bỏ trùng lặp (cùng Date + Category + Amount).

        Args:
            csv_path: Đường dẫn file .csv

        Returns:
            Số lượng giao dịch đã import thành công.
        """
        df_new = self._file_manager.import_from_csv(csv_path)
        return self._merge_and_save(df_new)

    def _merge_and_save(self, df_new: pd.DataFrame) -> int:
        """Merge DataFrame mới vào dữ liệu hiện có, loại trùng, lưu file."""
        df_existing = self._file_manager.load_data()
        df_merged   = pd.concat([df_existing, df_new], ignore_index=True)
        df_merged   = df_merged.drop_duplicates(
            subset=["Date", "Category", "Amount"], keep="first"
        )
        self._file_manager.save_all(df_merged)
        self._rebuild_analyzer()
        return len(df_new)

    # ── Quick stats ───────────────────────────────────────────────

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
                f"balance={self.balance:,.0f}đ)")
