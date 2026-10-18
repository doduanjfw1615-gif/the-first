"""
src/business/analyzer.py
========================
Business Layer: Financial data analysis engine.

Wraps a pandas DataFrame and exposes a clean, typed API
for the UI layer — no pandas leaks outside this module.

New in v6:
  - filter_by_period(year, month): filter to year/all or year+month
  - group_by_category_period: category breakdown for a period
  - get_monthly_report_period: monthly bar-chart data
  - get_balance_timeline_period: cumulative balance for a period
  - get_correlation_data: correlation matrix of numeric columns
  - get_kde_data: KDE (density) data per transaction type
  - get_available_periods: list of (year, month) tuples in dataset
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional


class FinancialAnalyzer:
    """
    Analyze financial transactions stored in a pandas DataFrame.

    Design: Wrapper/Facade pattern.
    - Receives raw DataFrame from the Data layer.
    - Provides a clean API for the UI layer.
    - All pandas logic is encapsulated here.

    Attributes:
        _df (pd.DataFrame): Cleaned internal DataFrame.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        """
        Initialize the analyzer with transaction data.

        Args:
            df: DataFrame with columns Date, Category, Type, Amount, Note.
        """
        self._df: pd.DataFrame = self._prepare(df.copy())

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column types and drop rows with invalid dates."""
        if df.empty:
            return df
        df["Date"]   = pd.to_datetime(df["Date"],   format="mixed", errors="coerce")
        df["Amount"] = pd.to_numeric(df["Amount"],  errors="coerce").fillna(0)
        df = df.dropna(subset=["Date"])
        return df

    def _filtered(self, year: Optional[int], month: Optional[int]) -> pd.DataFrame:
        """
        Return a subset filtered by year and/or month.

        Args:
            year:  Filter to this year. None = all years.
            month: Filter to this month (1-12). None = whole year.

        Returns:
            Filtered DataFrame (copy).
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
        Return all (year, month) pairs present in the dataset.

        Returns:
            Sorted list of (year, month) tuples, most recent first.
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
        """Return sorted list of years (descending) in the dataset."""
        if self._df.empty:
            return []
        return sorted(self._df["Date"].dt.year.dropna().unique().astype(int).tolist(),
                      reverse=True)

    def get_available_categories(self, tx_type: Optional[str] = None) -> list[str]:
        """Return sorted list of unique categories present in the dataset."""
        if self._df.empty:
            return []
        df = self._df
        if tx_type is not None and tx_type not in ("All", ""):
            df = df[df["Type"] == tx_type]
        cats = df["Category"].dropna().unique().tolist()
        return sorted([str(c) for c in cats if str(c).strip()])

    def filter_data(self,
                    year: Optional[int] = None,
                    month: Optional[int] = None,
                    tx_type: Optional[str] = None,
                    category: Optional[str] = None,
                    search: Optional[str] = None) -> pd.DataFrame:
        """
        Filter transactions by multiple criteria:
        year, month, transaction type, category, and text search (in Note & Category).
        """
        df = self._df
        if df.empty:
            return df
        if year is not None:
            df = df[df["Date"].dt.year == year]
        if month is not None:
            df = df[df["Date"].dt.month == month]
        if tx_type is not None and tx_type not in ("All", ""):
            df = df[df["Type"] == tx_type]
        if category is not None and category not in ("All", ""):
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
        """Total income, optionally filtered by year/month."""
        df = self._filtered(year, month)
        if df.empty:
            return 0.0
        return float(df[df["Type"] == "Income"]["Amount"].sum())

    def get_total_expense(self, year: Optional[int] = None,
                          month: Optional[int] = None) -> float:
        """Total expense, optionally filtered by year/month."""
        df = self._filtered(year, month)
        if df.empty:
            return 0.0
        return float(df[df["Type"] == "Expense"]["Amount"].sum())

    def get_balance(self, year: Optional[int] = None,
                    month: Optional[int] = None) -> float:
        """Net balance = income - expense for the given period."""
        return self.get_total_income(year, month) - self.get_total_expense(year, month)

    def get_avg_monthly_expense(self) -> float:
        """Average monthly expense across all data."""
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
        Aggregate summary for the dashboard cards.

        Args:
            year:  Optional year filter.
            month: Optional month filter (requires year).

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
            year:    Optional year filter.
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
            year:  Optional year filter.
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
            year:  Optional year filter.
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
            year:  Optional year filter.
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
