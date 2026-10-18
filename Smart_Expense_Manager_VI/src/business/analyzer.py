# -*- coding: utf-8 -*-
"""
src/business/analyzer.py
========================
Tầng Nghiệp vụ: Công cụ phân tích dữ liệu tài chính.

Bao bọc pandas DataFrame và cung cấp API rõ ràng
cho tầng UI — không để logic pandas rò rỉ ra ngoài.

Cải tiến v6:
  - filter_by_period(year, month): lọc theo năm/tháng
  - group_by_category_period: thống kê danh mục theo kỳ
  - get_monthly_report_period: dữ liệu biểu đồ cột theo tháng
  - get_balance_timeline_period: xu hướng số dư theo kỳ
  - get_correlation_data: ma trận tương quan các cột số
  - get_kde_data: dữ liệu KDE (mật độ) theo loại giao dịch
  - get_available_periods: danh sách (năm, tháng) trong dữ liệu
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional


class FinancialAnalyzer:
    """
    Phân tích giao dịch tài chính từ pandas DataFrame.

    Thiết kế: Wrapper/Facade pattern.
    - Nhận DataFrame thô từ tầng Data.
    - Cung cấp API sạch cho tầng UI.
    - Toàn bộ logic Pandas đóng gói tại đây.

    Attributes:
        _df (pd.DataFrame): DataFrame nội bộ đã chuẩn hóa.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        """
        Khởi tạo analyzer với dữ liệu giao dịch.

        Args:
            df: DataFrame với các cột Date, Category, Type, Amount, Note.
        """
        self._df: pd.DataFrame = self._prepare(df.copy())

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        """Chuẩn hóa kiểu cột và xóa hàng có ngày không hợp lệ."""
        if df.empty:
            return df
        df["Date"]   = pd.to_datetime(df["Date"],   format="mixed", errors="coerce")
        df["Amount"] = pd.to_numeric(df["Amount"],  errors="coerce").fillna(0)
        df = df.dropna(subset=["Date"])
        return df

    def _filtered(self, year: Optional[int], month: Optional[int]) -> pd.DataFrame:
        """
        Trả về tập con được lọc theo năm và/hoặc tháng.

        Args:
            year:  Lọc theo năm này. None = tất cả các năm.
            month: Lọc theo tháng (1-12). None = cả năm.

        Returns:
            DataFrame đã lọc (bản sao).
        """
        df = self._df
        if df.empty:
            return df
        if year is not None:
            df = df[df["Date"].dt.year == year]
        if month is not None and year is not None:
            df = df[df["Date"].dt.month == month]
        return df.copy()

    # ── Period metadata ───────────────────────────────────────────

    def get_available_periods(self) -> list[tuple[int, int]]:
        """
        Trả về tất cả cặp (năm, tháng) có trong dữ liệu.

        Returns:
            Danh sách (năm, tháng) sắp xếp giảm dần.
        """
        if self._df.empty:
            return []
        periods = (
            self._df["Date"]
            .dropna()
            .dt.to_period("M")
            .unique()
        )
        result = sorted(
            [(p.year, p.month) for p in periods],
            reverse=True,
        )
        return result

    def get_available_years(self) -> list[int]:
        """Trả về danh sách năm (giảm dần) có trong dữ liệu."""
        if self._df.empty:
            return []
        return sorted(self._df["Date"].dt.year.dropna().unique().astype(int).tolist(),
                      reverse=True)

    def get_available_categories(self, tx_type: Optional[str] = None) -> list[str]:
        """Trả về danh sách danh mục phân loại duy nhất có trong dữ liệu."""
        if self._df.empty:
            return []
        df = self._df
        if tx_type is not None and tx_type not in ("All", "Tất cả", ""):
            type_internal = "Income" if tx_type in ("Income", "Thu nhập", "Thu") else "Expense"
            df = df[df["Type"] == type_internal]
        cats = df["Category"].dropna().unique().tolist()
        return sorted([str(c) for c in cats if str(c).strip()])

    def filter_data(self,
                    year: Optional[int] = None,
                    month: Optional[int] = None,
                    tx_type: Optional[str] = None,
                    category: Optional[str] = None,
                    search: Optional[str] = None) -> pd.DataFrame:
        """
        Bộ lọc giao dịch đa tiêu chí:
        năm, tháng, loại giao dịch, danh mục, và tìm kiếm từ khóa (trong Ghi chú & Danh mục).
        """
        df = self._df
        if df.empty:
            return df
        if year is not None:
            df = df[df["Date"].dt.year == year]
        if month is not None:
            df = df[df["Date"].dt.month == month]
        if tx_type is not None and tx_type not in ("All", "Tất cả", ""):
            type_internal = "Income" if tx_type in ("Income", "Thu nhập", "Thu") else "Expense"
            df = df[df["Type"] == type_internal]
        if category is not None and category not in ("All", "Tất cả", ""):
            df = df[df["Category"] == category]
        if search:
            s = str(search).strip().lower()
            if s:
                note_m = df["Note"].astype(str).str.lower().str.contains(s, regex=False, na=False)
                cat_m  = df["Category"].astype(str).str.lower().str.contains(s, regex=False, na=False)
                df = df[note_m | cat_m]
        return df.copy()

    # ── Core totals ───────────────────────────────────────────────

    def get_total_income(self, year: Optional[int] = None,
                         month: Optional[int] = None) -> float:
        """Tổng thu nhập, có thể lọc theo năm/tháng."""
        df = self._filtered(year, month)
        if df.empty:
            return 0.0
        return float(df[df["Type"] == "Income"]["Amount"].sum())

    def get_total_expense(self, year: Optional[int] = None,
                          month: Optional[int] = None) -> float:
        """Tổng chi tiêu, có thể lọc theo năm/tháng."""
        df = self._filtered(year, month)
        if df.empty:
            return 0.0
        return float(df[df["Type"] == "Expense"]["Amount"].sum())

    def get_balance(self, year: Optional[int] = None,
                    month: Optional[int] = None) -> float:
        """Số dư = thu nhập - chi tiêu trong kỳ."""
        return self.get_total_income(year, month) - self.get_total_expense(year, month)

    def get_avg_monthly_expense(self) -> float:
        """Chi tiêu trung bình mỗi tháng trên toàn bộ dữ liệu."""
        if self._df.empty:
            return 0.0
        exp = self._df[self._df["Type"] == "Expense"].copy()
        if exp.empty:
            return 0.0
        exp["YM"] = exp["Date"].dt.to_period("M")
        return float(exp.groupby("YM")["Amount"].sum().mean())

    def get_summary_stats(self, year: Optional[int] = None,
                          month: Optional[int] = None) -> dict:
        """
        Thống kê tổng hợp cho các thẻ dashboard.

        Args:
            year:  Lọc theo năm (tùy chọn).
            month: Lọc theo tháng (cần kèm năm).

        Returns:
            dict with keys: total_income, total_expense, balance,
                            avg_monthly_expense, transaction_count,
                            income_count, expense_count.
        """
        df = self._filtered(year, month)
        inc = float(df[df["Type"] == "Income"]["Amount"].sum())  if not df.empty else 0.0
        exp = float(df[df["Type"] == "Expense"]["Amount"].sum()) if not df.empty else 0.0
        return {
            "total_income":        inc,
            "total_expense":       exp,
            "balance":             inc - exp,
            "avg_monthly_expense": self.get_avg_monthly_expense(),
            "transaction_count":   len(df),
            "income_count":        int((df["Type"] == "Income").sum())  if not df.empty else 0,
            "expense_count":       int((df["Type"] == "Expense").sum()) if not df.empty else 0,
        }

    # ── Category analysis ─────────────────────────────────────────

    def group_by_category(self, tx_type: str = "Expense",
                          year: Optional[int] = None,
                          month: Optional[int] = None) -> pd.Series:
        """
        Total amount per category for a given transaction type and period.

        Args:
            tx_type: "Expense" or "Income".
            year:    Lọc theo năm (tùy chọn).
            month:   Optional month filter.

        Returns:
            Series indexed by category, sorted descending.
        """
        df = self._filtered(year, month)
        if df.empty:
            return pd.Series(dtype=float)
        sub = df[df["Type"] == tx_type]
        if sub.empty:
            return pd.Series(dtype=float)
        return sub.groupby("Category")["Amount"].sum().sort_values(ascending=False)

    def get_category_percent(self, tx_type: str = "Expense",
                             year: Optional[int] = None,
                             month: Optional[int] = None) -> pd.Series:
        """Category breakdown as percentages."""
        totals = self.group_by_category(tx_type, year, month)
        if totals.empty or totals.sum() == 0:
            return pd.Series(dtype=float)
        return (totals / totals.sum() * 100).round(1)

    # ── Monthly report ────────────────────────────────────────────

    def get_monthly_report(self, year: Optional[int] = None) -> pd.DataFrame:
        """
        Monthly income/expense/balance report.

        Args:
            year: Restrict to this year. None = all years.

        Returns:
            DataFrame with columns: YearMonth, Income, Expense, Balance.
        """
        df = self._filtered(year, month=None)
        empty = pd.DataFrame(columns=["YearMonth", "Income", "Expense", "Balance"])
        if df.empty:
            return empty

        df = df.set_index("Date")
        inc = df[df["Type"] == "Income"]["Amount"].resample("ME").sum()
        exp = df[df["Type"] == "Expense"]["Amount"].resample("ME").sum()

        report = pd.DataFrame({"Income": inc, "Expense": exp}).fillna(0)
        report["Balance"] = report["Income"] - report["Expense"]
        report.index = report.index.to_period("M")
        report.index.name = "YearMonth"
        return report.reset_index()

    def get_monthly_report_labels(self, year: Optional[int] = None) -> tuple:
        """
        Convenience for bar-chart rendering.

        Returns:
            (labels, income_values, expense_values) as lists.
        """
        report = self.get_monthly_report(year)
        if report.empty:
            return [], [], []
        return (
            [str(p) for p in report["YearMonth"]],
            report["Income"].tolist(),
            report["Expense"].tolist(),
        )

    # ── Balance timeline ──────────────────────────────────────────

    def get_balance_timeline(self, year: Optional[int] = None,
                             month: Optional[int] = None) -> pd.DataFrame:
        """
        Cumulative balance over time.

        Args:
            year:  Lọc theo năm (tùy chọn).
            month: Optional month filter.

        Returns:
            DataFrame with columns: Date, CumulativeBalance.
        """
        df = self._filtered(year, month)
        if df.empty:
            return pd.DataFrame(columns=["Date", "CumulativeBalance"])

        df = df.sort_values("Date").copy()
        df["SignedAmount"] = df.apply(
            lambda r: r["Amount"] if r["Type"] == "Income" else -r["Amount"],
            axis=1,
        )
        df["CumulativeBalance"] = df["SignedAmount"].cumsum()
        return df[["Date", "CumulativeBalance"]].reset_index(drop=True)

    # ── Advanced analytics ────────────────────────────────────────

    def get_correlation_data(self, year: Optional[int] = None,
                             month: Optional[int] = None) -> pd.DataFrame:
        """
        Correlation matrix between Amount grouped by (Date x Category).

        Pivots the data so each category becomes a column, then
        computes Pearson correlation.

        Args:
            year:  Lọc theo năm (tùy chọn).
            month: Optional month filter.

        Returns:
            Correlation DataFrame, or empty if insufficient data.
        """
        df = self._filtered(year, month)
        if df.empty or len(df) < 4:
            return pd.DataFrame()

        try:
            pivot = df.pivot_table(
                index="Date",
                columns="Category",
                values="Amount",
                aggfunc="sum",
            ).fillna(0)
            if pivot.shape[1] < 2:
                return pd.DataFrame()
            return pivot.corr().round(2)
        except Exception:
            return pd.DataFrame()

    def get_kde_data(self, year: Optional[int] = None,
                     month: Optional[int] = None,
                     bins: int = 40) -> dict:
        """
        KDE / histogram data for expense and income distributions.

        Args:
            year:  Lọc theo năm (tùy chọn).
            month: Optional month filter.
            bins:  Number of histogram bins.

        Returns:
            dict with keys 'expense' and 'income', each a dict of
            {bin_edges, counts, kde_x, kde_y} or None if no data.
        """
        df = self._filtered(year, month)
        result: dict = {"expense": None, "income": None}

        for tx_type, key in [("Expense", "expense"), ("Income", "income")]:
            amounts = df[df["Type"] == tx_type]["Amount"].dropna().values
            if len(amounts) < 3:
                continue
            counts, edges = np.histogram(amounts, bins=bins)
            # Gaussian KDE
            from scipy.stats import gaussian_kde  # type: ignore
            try:
                kde    = gaussian_kde(amounts)
                kde_x  = np.linspace(amounts.min(), amounts.max(), 200)
                kde_y  = kde(kde_x)
            except Exception:
                kde_x = kde_y = np.array([])
            result[key] = {
                "bin_edges": edges,
                "counts":    counts,
                "kde_x":     kde_x,
                "kde_y":     kde_y,
                "mean":      float(amounts.mean()),
                "median":    float(np.median(amounts)),
            }
        return result

    # ── Budget checking ───────────────────────────────────────────

    def check_budget_alerts(self, budgets: dict,
                             month: Optional[str] = None) -> list[dict]:
        """
        Check which categories exceed their budget limit.

        Args:
            budgets: {category: limit_amount}.
            month:   "YYYY-MM" string, or None for current/latest month.

        Returns:
            List of dicts: category, spent, limit, percent, over.
        """
        if self._df.empty or not budgets:
            return []

        df = self._df.copy()
        df["Period"] = df["Date"].dt.to_period("M")
        if month:
            target = pd.Period(month, freq="M")
        else:
            curr = pd.Timestamp.now().to_period("M")
            if (df["Period"] == curr).any():
                target = curr
            else:
                target = df["Period"].max() if not df.empty else curr

        monthly = (
            df[(df["Type"] == "Expense") & (df["Period"] == target)]
            .groupby("Category")["Amount"].sum()
        )
        alerts = []
        for category, limit in budgets.items():
            spent   = float(monthly.get(category, 0))
            pct     = (spent / limit * 100) if limit > 0 else 0
            alerts.append({
                "category": category,
                "spent":    spent,
                "limit":    float(limit),
                "percent":  round(pct, 1),
                "over":     spent > limit,
                "period":   str(target),
            })
        return sorted(alerts, key=lambda x: x["percent"], reverse=True)

    # ── Read-only DataFrame access ─────────────────────────────────

    @property
    def df(self) -> pd.DataFrame:
        """Read-only copy of the internal DataFrame."""
        return self._df.copy()
