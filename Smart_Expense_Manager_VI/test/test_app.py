"""
test/test_app.py
Unit tests cho toàn bộ project Smart Expense Manager.
Kiểm thử: Model, Analyzer, Wallet, FileManager.
"""

import sys
import os
import unittest
import tempfile
import pandas as pd
from pathlib import Path
from datetime import datetime

# Thêm project root vào sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.transaction import (
    Transaction, IncomeTransaction, ExpenseTransaction, TransactionFactory
)
from src.data.file_manager import TransactionFileManager
from src.business.analyzer import FinancialAnalyzer
from src.business.wallet import Wallet


# ════════════════════════════════════════════════════════
# 1. Model Tests
# ════════════════════════════════════════════════════════

class TestTransactionModel(unittest.TestCase):
    """Kiểm thử lớp Transaction và tính kế thừa/đa hình."""

    def test_income_signed_amount_positive(self):
        """IncomeTransaction.get_signed_amount() phải trả về giá trị DƯƠNG."""
        tx = IncomeTransaction("2024-01-01", "Salary", 5_000_000)
        self.assertEqual(tx.get_signed_amount(), +5_000_000)

    def test_expense_signed_amount_negative(self):
        """ExpenseTransaction.get_signed_amount() phải trả về giá trị ÂM."""
        tx = ExpenseTransaction("2024-01-02", "Food", 100_000)
        self.assertEqual(tx.get_signed_amount(), -100_000)

    def test_income_get_type(self):
        tx = IncomeTransaction("2024-01-01", "Salary", 1_000_000)
        self.assertEqual(tx.get_type(), "Income")

    def test_expense_get_type(self):
        tx = ExpenseTransaction("2024-01-01", "Food", 50_000)
        self.assertEqual(tx.get_type(), "Expense")

    def test_polymorphism_via_base_reference(self):
        """Đa hình: cùng interface, hành vi khác nhau."""
        transactions: list[Transaction] = [
            IncomeTransaction("2024-01-01", "Salary", 10_000_000),
            ExpenseTransaction("2024-01-02", "Rent",   4_000_000),
            ExpenseTransaction("2024-01-03", "Food",     200_000),
        ]
        total = sum(tx.get_signed_amount() for tx in transactions)
        self.assertAlmostEqual(total, 5_800_000)

    def test_invalid_amount_raises_error(self):
        """Số tiền <= 0 phải raise ValueError."""
        with self.assertRaises(ValueError):
            IncomeTransaction("2024-01-01", "Salary", -1000)

    def test_zero_amount_raises_error(self):
        with self.assertRaises(ValueError):
            ExpenseTransaction("2024-01-01", "Food", 0)

    def test_invalid_date_raises_error(self):
        """Ngày tháng sai định dạng phải raise ValueError."""
        with self.assertRaises(ValueError):
            IncomeTransaction("30/02/2024", "Salary", 1_000_000)

    def test_valid_date_formats(self):
        """Chấp nhận nhiều định dạng ngày."""
        tx1 = IncomeTransaction("2024-01-15", "Salary", 1_000_000)
        tx2 = IncomeTransaction("15/01/2024", "Salary", 1_000_000)
        self.assertEqual(tx1.date.day, 15)
        self.assertEqual(tx2.date.month, 1)

    def test_to_dict(self):
        """to_dict() phải trả về đúng keys."""
        tx = ExpenseTransaction("2024-03-10", "Food", 150_000, "Ăn sáng")
        d = tx.to_dict()
        self.assertIn("Date", d)
        self.assertIn("Amount", d)
        self.assertEqual(d["Type"], "Expense")
        self.assertEqual(d["Note"], "Ăn sáng")


class TestTransactionFactory(unittest.TestCase):
    """Kiểm thử Factory Pattern."""

    def test_create_income(self):
        tx = TransactionFactory.create("2024-01-01", "Salary", "Income", 5_000_000)
        self.assertIsInstance(tx, IncomeTransaction)

    def test_create_expense(self):
        tx = TransactionFactory.create("2024-01-01", "Food", "Expense", 100_000)
        self.assertIsInstance(tx, ExpenseTransaction)

    def test_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            TransactionFactory.create("2024-01-01", "Food", "Unknown", 100_000)


# ════════════════════════════════════════════════════════
# 2. Analyzer Tests
# ════════════════════════════════════════════════════════

class TestFinancialAnalyzer(unittest.TestCase):
    """Kiểm thử tính toán Pandas trong FinancialAnalyzer."""

    def setUp(self):
        """Tạo DataFrame mẫu trước mỗi test."""
        self.df = pd.DataFrame({
            "Date":     ["2024-01-01", "2024-01-02", "2024-01-03",
                         "2024-02-01", "2024-02-10"],
            "Category": ["Salary",     "Food",       "Rent",
                         "Salary",     "Food"],
            "Type":     ["Income",     "Expense",    "Expense",
                         "Income",     "Expense"],
            "Amount":   [20_000_000,   200_000,      4_000_000,
                         20_000_000,   300_000],
            "Note":     ["",           "",           "",
                         "",           ""],
        })
        self.df["Date"] = pd.to_datetime(self.df["Date"])
        self.analyzer = FinancialAnalyzer(self.df)

    def test_total_income(self):
        self.assertEqual(self.analyzer.get_total_income(), 40_000_000)

    def test_total_expense(self):
        self.assertEqual(self.analyzer.get_total_expense(), 4_500_000)

    def test_balance(self):
        expected = 40_000_000 - 4_500_000
        self.assertAlmostEqual(self.analyzer.get_balance(), expected)

    def test_group_by_category_expense(self):
        """groupby('Category') cho Expense."""
        series = self.analyzer.group_by_category("Expense")
        self.assertEqual(series["Rent"], 4_000_000)
        self.assertEqual(series["Food"], 500_000)

    def test_group_by_category_income(self):
        series = self.analyzer.group_by_category("Income")
        self.assertEqual(series["Salary"], 40_000_000)

    def test_monthly_report_structure(self):
        """get_monthly_report() trả về DataFrame với cột Income, Expense, Balance."""
        report = self.analyzer.get_monthly_report()
        self.assertIn("Income",  report.columns)
        self.assertIn("Expense", report.columns)
        self.assertIn("Balance", report.columns)
        # Phải có 2 tháng (Jan và Feb)
        self.assertEqual(len(report), 2)

    def test_monthly_report_values(self):
        report = self.analyzer.get_monthly_report()
        jan_row = report[report["YearMonth"].astype(str).str.startswith("2024-01")]
        self.assertFalse(jan_row.empty)
        self.assertEqual(jan_row.iloc[0]["Income"], 20_000_000)

    def test_balance_timeline_cumulative(self):
        """Số dư cộng dồn tăng/giảm đúng theo thứ tự."""
        tl = self.analyzer.get_balance_timeline()
        self.assertFalse(tl.empty)
        self.assertIn("CumulativeBalance", tl.columns)
        last_balance = tl.iloc[-1]["CumulativeBalance"]
        self.assertAlmostEqual(last_balance, 40_000_000 - 4_500_000)

    def test_budget_alert_over_limit(self):
        """Cảnh báo khi chi tiêu vượt hạn mức."""
        # Đặt budget thấp hơn chi tiêu thực tế tháng 1
        budgets = {"Food": 100_000}  # Limit 100k nhưng thực tế 200k
        alerts = self.analyzer.check_budget_alerts(budgets, month="2024-01")
        food_alert = next((a for a in alerts if a["category"] == "Food"), None)
        self.assertIsNotNone(food_alert)
        self.assertTrue(food_alert["over"])

    def test_budget_alert_within_limit(self):
        """Không cảnh báo khi chi tiêu trong hạn mức."""
        budgets = {"Food": 1_000_000}  # Limit 1M > chi tiêu thực
        alerts = self.analyzer.check_budget_alerts(budgets, month="2024-01")
        food_alert = next((a for a in alerts if a["category"] == "Food"), None)
        self.assertIsNotNone(food_alert)
        self.assertFalse(food_alert["over"])

    def test_empty_dataframe(self):
        """Analyzer với DataFrame rỗng không raise exception."""
        empty_analyzer = FinancialAnalyzer(pd.DataFrame())
        self.assertEqual(empty_analyzer.get_balance(), 0.0)
        self.assertEqual(empty_analyzer.get_total_income(), 0.0)
        self.assertTrue(empty_analyzer.group_by_category().empty)


# ════════════════════════════════════════════════════════
# 3. FileManager Tests
# ════════════════════════════════════════════════════════

class TestTransactionFileManager(unittest.TestCase):
    """Kiểm thử đọc/ghi file CSV."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.tmpdir, "test_tx.csv")
        self.fm = TransactionFileManager(self.csv_path)

    def test_creates_file_on_init(self):
        self.assertTrue(Path(self.csv_path).exists())

    def test_save_and_load_transaction(self):
        tx = IncomeTransaction("2024-06-01", "Salary", 15_000_000, "Test")
        self.fm.save_transaction(tx)

        df = self.fm.load_data()
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Type"], "Income")
        self.assertAlmostEqual(df.iloc[0]["Amount"], 15_000_000)

    def test_save_multiple_transactions(self):
        for i in range(5):
            tx = ExpenseTransaction(f"2024-0{i+1}-01", "Food", (i+1)*100_000)
            self.fm.save_transaction(tx)
        df = self.fm.load_data()
        self.assertEqual(len(df), 5)

    def test_delete_transaction(self):
        tx = IncomeTransaction("2024-07-01", "Salary", 20_000_000)
        self.fm.save_transaction(tx)
        result = self.fm.delete_transaction(0)
        self.assertTrue(result)
        df = self.fm.load_data()
        self.assertEqual(len(df), 0)

    def test_load_empty_file(self):
        df = self.fm.load_data()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 0)

    def test_budget_save_and_load(self):
        budgets = {"Food": 3_000_000, "Rent": 5_000_000}
        self.fm.save_budgets(budgets)
        loaded = self.fm.load_budgets()
        self.assertEqual(loaded["Food"], 3_000_000)
        self.assertEqual(loaded["Rent"], 5_000_000)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ════════════════════════════════════════════════════════
# 4. Wallet Tests (Encapsulation)
# ════════════════════════════════════════════════════════

class TestWallet(unittest.TestCase):
    """Kiểm thử Wallet – tính đóng gói và tích hợp."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.tmpdir, "wallet_test.csv")
        self.wallet = Wallet(self.csv_path)

    def test_private_transactions_not_accessible(self):
        """Không thể truy cập __transactions trực tiếp từ ngoài."""
        self.assertFalse(hasattr(self.wallet, "__transactions"))
        self.assertFalse(hasattr(self.wallet, "_transactions"))

    def test_add_transaction_via_method(self):
        """Chỉ thêm được qua add_transaction() (Encapsulation)."""
        self.wallet.add_transaction("2024-01-01", "Salary", "Income", 10_000_000)
        self.assertEqual(self.wallet.get_transaction_count(), 1)

    def test_balance_calculation(self):
        self.wallet.add_transaction("2024-01-01", "Salary",  "Income",  20_000_000)
        self.wallet.add_transaction("2024-01-02", "Food",    "Expense",  1_000_000)
        self.wallet.add_transaction("2024-01-03", "Rent",    "Expense",  4_000_000)
        self.assertAlmostEqual(self.wallet.balance, 15_000_000)

    def test_total_income_total_expense(self):
        self.wallet.add_transaction("2024-02-01", "Salary", "Income",  20_000_000)
        self.wallet.add_transaction("2024-02-05", "Food",   "Expense",  2_000_000)
        self.assertAlmostEqual(self.wallet.total_income,  20_000_000)
        self.assertAlmostEqual(self.wallet.total_expense,  2_000_000)

    def test_delete_transaction(self):
        self.wallet.add_transaction("2024-01-01", "Salary", "Income", 5_000_000)
        self.assertEqual(self.wallet.get_transaction_count(), 1)
        self.wallet.delete_transaction(0)
        self.assertEqual(self.wallet.get_transaction_count(), 0)

    def test_set_budget_and_get_alerts(self):
        self.wallet.add_transaction("2024-01-05", "Food", "Expense", 500_000)
        self.wallet.set_budget("Food", 200_000)  # Limit < spent → alert
        alerts = self.wallet.get_budget_alerts(month="2024-01")
        self.assertTrue(any(a["over"] for a in alerts if a["category"] == "Food"))

    def test_invalid_transaction_raises(self):
        with self.assertRaises(ValueError):
            self.wallet.add_transaction("bad-date", "Food", "Expense", 100_000)

    def test_get_all_transactions_returns_copy(self):
        """Không cho phép thay đổi list nội bộ qua reference."""
        self.wallet.add_transaction("2024-01-01", "Salary", "Income", 5_000_000)
        txs = self.wallet.get_all_transactions()
        original_count = self.wallet.get_transaction_count()
        txs.append("hack")  # Thêm vào bản sao
        self.assertEqual(self.wallet.get_transaction_count(), original_count)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ════════════════════════════════════════════════════════
# 5. Edge Case / Integration Tests
# ════════════════════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    """Kiểm thử các trường hợp biên."""

    def test_large_amount(self):
        tx = IncomeTransaction("2024-01-01", "Salary", 999_999_999_999)
        self.assertEqual(tx.amount, 999_999_999_999)

    def test_special_characters_in_note(self):
        tx = ExpenseTransaction("2024-01-01", "Food", 50_000, "Ăn phở bò 🍜 tại Hà Nội")
        self.assertIn("Hà Nội", tx.note)

    def test_transaction_repr(self):
        tx = IncomeTransaction("2024-06-15", "Bonus", 3_000_000)
        self.assertIn("IncomeTransaction", repr(tx))
        self.assertIn("Bonus", repr(tx))

    def test_analyzer_single_transaction(self):
        """Analyzer với 1 giao dịch không lỗi."""
        df = pd.DataFrame({
            "Date": [pd.Timestamp("2024-01-01")],
            "Category": ["Food"],
            "Type": ["Expense"],
            "Amount": [100_000],
            "Note": [""],
        })
        analyzer = FinancialAnalyzer(df)
        self.assertEqual(analyzer.get_total_expense(), 100_000)
        self.assertEqual(analyzer.get_balance(), -100_000)

    def test_groupby_no_expense_data(self):
        """group_by_category trả về Series rỗng nếu không có dữ liệu."""
        df = pd.DataFrame({
            "Date": [pd.Timestamp("2024-01-01")],
            "Category": ["Salary"],
            "Type": ["Income"],
            "Amount": [10_000_000],
            "Note": [""],
        })
        analyzer = FinancialAnalyzer(df)
        result = analyzer.group_by_category("Expense")
        self.assertTrue(result.empty)

    def test_monthly_resample_correct_months(self):
        """resample phải tạo đúng số tháng."""
        data = []
        for month in range(1, 7):
            data.append({
                "Date": pd.Timestamp(f"2024-{month:02d}-01"),
                "Category": "Food",
                "Type": "Expense",
                "Amount": 100_000,
                "Note": "",
            })
        df = pd.DataFrame(data)
        analyzer = FinancialAnalyzer(df)
        report = analyzer.get_monthly_report()
        self.assertEqual(len(report), 6)


# ════════════════════════════════════════════════════════
# 5. Standardization & New Features Tests
# ════════════════════════════════════════════════════════

class TestNewStandardizationFeatures(unittest.TestCase):
    """Kiểm thử chuẩn hóa ngày giờ, lọc đa tiêu chí, danh mục lộc/lì xì và tiền tệ."""

    def test_datetime_with_hours_minutes(self):
        """Transaction chấp nhận định dạng ngày giờ DD/MM/YYYY HH:MM và YYYY-MM-DD HH:MM."""
        tx1 = TransactionFactory.create("2026-04-15 14:30", "Ăn uống", "Expense", 50_000, "Cà phê chiều")
        self.assertEqual(tx1.date.strftime("%Y-%m-%d %H:%M"), "2026-04-15 14:30")

        tx2 = TransactionFactory.create("15/04/2026 09:15", "Lộc / Lì xì", "Income", 200_000, "Lì xì tết")
        self.assertEqual(tx2.date.strftime("%d/%m/%Y %H:%M"), "15/04/2026 09:15")
        self.assertIn("₫", repr(tx2))

    def test_filter_data_multi_criteria(self):
        """FinancialAnalyzer.filter_data lọc chính xác theo năm, tháng, loại, danh mục và từ khóa."""
        df = pd.DataFrame([
            {"Date": pd.Timestamp("2025-05-01 10:00"), "Category": "Ăn uống", "Type": "Expense", "Amount": 100_000, "Note": "Bún chả"},
            {"Date": pd.Timestamp("2025-05-15 12:00"), "Category": "Ăn uống", "Type": "Expense", "Amount": 200_000, "Note": "Phở bò"},
            {"Date": pd.Timestamp("2025-06-01 08:00"), "Category": "Lương", "Type": "Income", "Amount": 20_000_000, "Note": "Lương tháng 5"},
            {"Date": pd.Timestamp("2026-01-01 09:00"), "Category": "Lộc / Lì xì", "Type": "Income", "Amount": 1_000_000, "Note": "Mừng tuổi"},
        ])
        analyzer = FinancialAnalyzer(df)

        # Lọc theo năm 2025
        res_yr = analyzer.filter_data(year=2025)
        self.assertEqual(len(res_yr), 3)

        # Lọc theo tháng 5/2025
        res_mo = analyzer.filter_data(year=2025, month=5)
        self.assertEqual(len(res_mo), 2)

        # Lọc theo loại Expense
        res_type = analyzer.filter_data(tx_type="Expense")
        self.assertEqual(len(res_type), 2)

        # Lọc theo danh mục Ăn uống
        res_cat = analyzer.filter_data(category="Ăn uống")
        self.assertEqual(len(res_cat), 2)

        # Tìm kiếm theo từ khóa 'Phở'
        res_search = analyzer.filter_data(search="phở")
        self.assertEqual(len(res_search), 1)
        self.assertEqual(res_search.iloc[0]["Note"], "Phở bò")

    def test_cross_language_csv_import(self):
        """FileManager import CSV với tiêu đề tiếng Việt hoặc tiếng Anh và dịch danh mục."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", encoding="utf-8")
        tmp.write("Ngày,Loại,Danh Mục,Số Tiền,Ghi Chú\n2026-01-10 10:00,Thu nhập,Salary,15000000,Tiền lương tháng\n")
        tmp.close()

        fm = TransactionFileManager(tempfile.mktemp(suffix=".csv"))
        df = fm.import_from_csv(tmp.name)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Type"], "Income")
        self.assertEqual(df.iloc[0]["Category"], "Lương")
        os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
