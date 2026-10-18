"""
src/ui/app_gui.py
=================
Presentation Layer: Tkinter GUI for Smart Expense Manager.

Tabs:
  - Dashboard   : summary cards + pie chart + balance trend
  - Transactions: form + history table with month/year filter
  - Charts      : bar chart, correlation heatmap, KDE density
                  with chart-type selector + period filter
  - Budget      : set limits + alert progress bars

Performance (v6):
  - Fixed canvases reused across redraws (no Figure recreation)
  - draw_idle() instead of draw()
  - Charts scheduled with after_idle() to keep UI responsive
  - Bulk delete: 1 file write instead of N writes
  - Threading + progress bar for all heavy I/O tasks
"""

from __future__ import annotations

import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.business.wallet import Wallet

# ── Color palette (Catppuccin Mocha dark theme) ───────────────────
COLORS: dict[str, object] = {
    "bg":          "#1e1e2e",
    "surface":     "#2a2a3e",
    "card":        "#313244",
    "accent":      "#89b4fa",
    "green":       "#a6e3a1",
    "red":         "#f38ba8",
    "yellow":      "#f9e2af",
    "text":        "#cdd6f4",
    "subtext":     "#a6adc8",
    "border":      "#45475a",
    "income_bar":  "#a6e3a1",
    "expense_bar": "#f38ba8",
    "line":        "#89b4fa",
    "corr_pos":    "#89b4fa",
    "corr_neg":    "#f38ba8",
    "pie_colors":  ["#89b4fa", "#a6e3a1", "#f38ba8", "#f9e2af",
                    "#cba6f7", "#fab387", "#94e2d5", "#89dceb",
                    "#b4befe", "#eba0ac"],
}

FONT_TITLE  = ("Segoe UI", 18, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_BODY   = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)

CHART_TYPES: list[str] = [
    "Bar Chart (Monthly)",
    "Correlation Heatmap",
    "KDE Density",
]


def _fmt(amount: float) -> str:
    """Format a USD amount with thousands separator."""
    return f"${amount:,.2f}"


def _fmt_axis(value: float, _pos) -> str:
    """Smart axis formatter for USD amounts."""
    if abs(value) >= 1_000_000:
        return f"${value/1e6:.1f}M"
    elif abs(value) >= 1_000:
        return f"${value/1e3:.1f}K"
    else:
        return f"${value:.0f}"


class SmartExpenseApp(tk.Tk):
    """Main application window for Smart Expense Manager."""

    def __init__(self, data_file: str = "transactions.csv") -> None:
        super().__init__()
        self.wallet: Wallet = Wallet(data_file)

        self._pie_canvas:      Optional[FigureCanvasTkAgg] = None
        self._timeline_canvas: Optional[FigureCanvasTkAgg] = None
        self._chart_canvas:    Optional[FigureCanvasTkAgg] = None
        self._pie_fig:         Optional[Figure] = None
        self._timeline_fig:    Optional[Figure] = None
        self._chart_fig:       Optional[Figure] = None

        self._filter_year:  Optional[int] = None
        self._filter_month: Optional[int] = None
        self._chart_year:  Optional[int] = None
        self._chart_month: Optional[int] = None
        self._chart_pending: bool = False

        self._setup_window()
        self._apply_theme()
        self._build_ui()
        self.refresh_all()

    def _setup_window(self) -> None:
        self.title("💰 Smart Expense Manager")
        self.geometry("1340x820")
        self.minsize(1024, 680)
        self.configure(bg=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _apply_theme(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=COLORS["bg"], foreground=COLORS["text"],
                    fieldbackground=COLORS["card"], bordercolor=COLORS["border"],
                    troughcolor=COLORS["surface"], font=FONT_BODY)
        s.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=COLORS["surface"],
                    foreground=COLORS["subtext"], padding=[18, 8], font=FONT_BODY)
        s.map("TNotebook.Tab",
              background=[("selected", COLORS["card"])],
              foreground=[("selected", COLORS["accent"])],
              font=[("selected", ("Segoe UI", 10, "bold"))])
        for sty, bg, fg, fnt in [
            ("TFrame",  COLORS["bg"],   COLORS["text"],    FONT_BODY),
            ("TLabel",  COLORS["bg"],   COLORS["text"],    FONT_BODY),
            ("Card.TLabel", COLORS["card"], COLORS["text"], FONT_BODY),
        ]:
            s.configure(sty, background=bg, foreground=fg)
        s.configure("Value.TLabel",  background=COLORS["card"], foreground=COLORS["text"],  font=("Segoe UI", 22, "bold"))
        s.configure("Green.TLabel",  background=COLORS["card"], foreground=COLORS["green"], font=("Segoe UI", 22, "bold"))
        s.configure("Red.TLabel",    background=COLORS["card"], foreground=COLORS["red"],   font=("Segoe UI", 22, "bold"))
        s.configure("Accent.TButton", background=COLORS["accent"], foreground=COLORS["bg"],
                    font=("Segoe UI", 10, "bold"), borderwidth=0, padding=[12, 6])
        s.map("Accent.TButton", background=[("active", "#b4cefa")])
        s.configure("Danger.TButton",  background=COLORS["red"], foreground=COLORS["bg"],
                    font=("Segoe UI", 10, "bold"), borderwidth=0, padding=[12, 6])
        s.configure("Treeview", background=COLORS["surface"], foreground=COLORS["text"],
                    fieldbackground=COLORS["surface"], rowheight=28)
        s.configure("Treeview.Heading", background=COLORS["card"],
                    foreground=COLORS["accent"], font=("Segoe UI", 9, "bold"))
        s.map("Treeview",
              background=[("selected", COLORS["accent"])],
              foreground=[("selected", COLORS["bg"])])
        s.configure("TScrollbar", background=COLORS["surface"],
                    troughcolor=COLORS["bg"], borderwidth=0)
        s.configure("Indeterminate.Horizontal.TProgressbar",
                    troughcolor=COLORS["surface"], background=COLORS["accent"], thickness=8)

    def _build_ui(self) -> None:
        hdr = tk.Frame(self, bg=COLORS["surface"], height=60)
        hdr.pack(fill=tk.X, side=tk.TOP)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="💰 Smart Expense Manager", font=FONT_TITLE,
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(side=tk.LEFT, padx=20, pady=12)
        self._lbl_clock = tk.Label(hdr, text="", font=FONT_SMALL,
                                   bg=COLORS["surface"], fg=COLORS["subtext"])
        self._lbl_clock.pack(side=tk.RIGHT, padx=20)
        self._tick()

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tab_dash   = ttk.Frame(nb)
        self.tab_input  = ttk.Frame(nb)
        self.tab_charts = ttk.Frame(nb)
        self.tab_budget = ttk.Frame(nb)
        nb.add(self.tab_dash,   text="📊  Dashboard")
        nb.add(self.tab_input,  text="➕  Transactions")
        nb.add(self.tab_charts, text="📈  Charts")
        nb.add(self.tab_budget, text="🎯  Budget")

        self._build_dashboard()
        self._build_input_tab()
        self._build_charts_tab()
        self._build_budget_tab()

    def _tick(self) -> None:
        self._lbl_clock.config(text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.after(1000, self._tick)

    # ── Dashboard ─────────────────────────────────────────────────

    def _build_dashboard(self) -> None:
        frame = self.tab_dash
        cf = tk.Frame(frame, bg=COLORS["bg"])
        cf.pack(fill=tk.X, padx=16, pady=16)
        self._card_balance = self._stat_card(cf, "💰 Balance",       "$0.00", "Value.TLabel")
        self._card_income  = self._stat_card(cf, "📥 Total Income",  "$0.00", "Green.TLabel")
        self._card_expense = self._stat_card(cf, "📤 Total Expense", "$0.00", "Red.TLabel")
        self._card_avg     = self._stat_card(cf, "📅 Avg/Month",     "$0.00", "Value.TLabel")
        for c, _ in [self._card_balance, self._card_income,
                     self._card_expense, self._card_avg]:
            c.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=6)
        cr = tk.Frame(frame, bg=COLORS["bg"])
        cr.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        self._pie_frame = tk.Frame(cr, bg=COLORS["card"])
        self._pie_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        tk.Label(self._pie_frame, text="🥧 Expense Breakdown",
                 bg=COLORS["card"], fg=COLORS["accent"], font=FONT_HEADER).pack(pady=(10, 0))
        self._pie_area = tk.Frame(self._pie_frame, bg=COLORS["card"])
        self._pie_area.pack(fill=tk.BOTH, expand=True)
        self._tl_frame = tk.Frame(cr, bg=COLORS["card"])
        self._tl_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(self._tl_frame, text="📈 Balance Trend",
                 bg=COLORS["card"], fg=COLORS["accent"], font=FONT_HEADER).pack(pady=(10, 0))
        self._tl_area = tk.Frame(self._tl_frame, bg=COLORS["card"])
        self._tl_area.pack(fill=tk.BOTH, expand=True)

    def _stat_card(self, parent, title: str, value: str, style: str) -> tuple:
        card = tk.Frame(parent, bg=COLORS["card"])
        tk.Label(card, text=title, bg=COLORS["card"],
                 fg=COLORS["subtext"], font=FONT_SMALL).pack(padx=16, pady=(12, 2))
        lbl = ttk.Label(card, text=value, style=style)
        lbl.pack(padx=16, pady=(0, 12))
        return card, lbl

    # ── Transactions Tab ──────────────────────────────────────────

    def _build_input_tab(self) -> None:
        frame = self.tab_input
        left  = tk.Frame(frame, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=16)
        right = tk.Frame(frame, bg=COLORS["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 16), pady=16)

        fc = tk.Frame(left, bg=COLORS["card"])
        fc.pack(fill=tk.X)
        tk.Label(fc, text="➕ Add New Transaction", bg=COLORS["card"],
                 fg=COLORS["accent"], font=FONT_HEADER).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(14, 10))

        self._entry_date = self._entry(fc, datetime.now().strftime("%Y-%m-%d %H:%M"))

        self._income_cats  = ["Salary", "Bonus", "Savings", "Investment", "Business", "Other Income"]
        self._expense_cats = ["Food", "Rent", "Transport", "Entertainment",
                              "Healthcare", "Education", "Utilities", "Shopping", "Other Expense"]

        self._type_var = tk.StringVar(value="Expense")
        self._type_var.trace_add("write", self._on_type_changed)
        self._om_type = tk.OptionMenu(fc, self._type_var, "Expense", "Income")
        self._om_type.config(bg=COLORS["red"], fg=COLORS["bg"],
                             activebackground=COLORS["red"], activeforeground=COLORS["bg"],
                             relief=tk.FLAT, font=FONT_BODY, bd=0, highlightthickness=0,
                             cursor="hand2")
        self._om_type["menu"].config(bg=COLORS["surface"], fg=COLORS["text"],
                                     activebackground=COLORS["accent"],
                                     activeforeground=COLORS["bg"], font=FONT_BODY)

        self._cat_var = tk.StringVar(value="Food")
        self._om_cat  = tk.OptionMenu(fc, self._cat_var, *self._expense_cats)
        self._om_cat.config(bg=COLORS["accent"], fg=COLORS["bg"],
                            activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
                            relief=tk.FLAT, font=FONT_BODY, bd=0, highlightthickness=0,
                            cursor="hand2")
        self._om_cat["menu"].config(bg=COLORS["surface"], fg=COLORS["text"],
                                    activebackground=COLORS["accent"],
                                    activeforeground=COLORS["bg"], font=FONT_BODY)

        self._entry_amount = self._entry(fc)
        self._entry_note   = self._entry(fc)

        fields = [
            ("Date & Time (YYYY-MM-DD HH:MM) *", self._entry_date),
            ("Transaction Type *",              self._om_type),
            ("Category *",                      self._om_cat),
            ("Amount ($) *",                    self._entry_amount),
            ("Note",                            self._entry_note),
        ]
        for i, (lbl, w) in enumerate(fields, start=1):
            tk.Label(fc, text=lbl, bg=COLORS["card"], fg=COLORS["subtext"],
                     font=FONT_SMALL).grid(row=i, column=0, sticky=tk.W, padx=16, pady=4)
            w.grid(row=i, column=1, sticky=tk.EW, padx=16, pady=4, ipady=4)
        fc.columnconfigure(1, weight=1)

        bf = tk.Frame(fc, bg=COLORS["card"])
        bf.grid(row=len(fields)+1, column=0, columnspan=2, padx=16, pady=14)
        for txt, cmd, pad in [
            ("✅ Add",         self.add_transaction,  (0, 8)),
            ("📂 Import Excel", self.import_excel,    (0, 8)),
            ("📄 Import CSV",   self.import_csv,      (0, 8)),
            ("📁 New File",     self.create_new_file, (0, 0)),
        ]:
            ttk.Button(bf, text=txt, style="Accent.TButton",
                       command=cmd).pack(side=tk.LEFT, padx=pad)

        lc = tk.Frame(right, bg=COLORS["card"])
        lc.pack(fill=tk.BOTH, expand=True)

        hf = tk.Frame(lc, bg=COLORS["card"])
        hf.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(hf, text="📋 Transaction History", bg=COLORS["card"],
                 fg=COLORS["accent"], font=FONT_HEADER).pack(side=tk.LEFT)
        ttk.Button(hf, text="🗑 Delete All",
                   style="Danger.TButton", command=self.delete_all).pack(
            side=tk.RIGHT, padx=(4, 0))
        ttk.Button(hf, text="🗑 Delete Selected",
                   style="Danger.TButton", command=self.delete_selected).pack(
            side=tk.RIGHT)
        tk.Label(hf, text="Ctrl+Click = multi-select",
                 bg=COLORS["card"], fg=COLORS["subtext"],
                 font=FONT_SMALL).pack(side=tk.RIGHT, padx=(0, 8))

        # ── Comprehensive Filter Bar (Lọc) ──
        ff = tk.Frame(lc, bg=COLORS["card"])
        ff.pack(fill=tk.X, padx=12, pady=(0, 2))

        tk.Label(ff, text="Filter:", bg=COLORS["card"],
                 fg=COLORS["accent"], font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))

        self._filter_year_var   = tk.StringVar(value="All")
        self._filter_month_var  = tk.StringVar(value="All")
        self._filter_type_var   = tk.StringVar(value="All")
        self._filter_cat_var    = tk.StringVar(value="All")
        self._filter_search_var = tk.StringVar(value="")

        # Year dropdown
        tk.Label(ff, text="Yr:", bg=COLORS["card"], fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._om_filter_year = tk.OptionMenu(ff, self._filter_year_var, "All")
        self._style_menu(self._om_filter_year, width=5)
        self._om_filter_year.pack(side=tk.LEFT, padx=2)

        # Month dropdown
        tk.Label(ff, text="Mo:", bg=COLORS["card"], fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._om_filter_month = tk.OptionMenu(ff, self._filter_month_var, "All")
        self._style_menu(self._om_filter_month, width=4)
        self._om_filter_month.pack(side=tk.LEFT, padx=2)

        # Type dropdown
        tk.Label(ff, text="Type:", bg=COLORS["card"], fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._om_filter_type = tk.OptionMenu(ff, self._filter_type_var, "All", "Income", "Expense")
        self._style_menu(self._om_filter_type, width=7)
        self._om_filter_type.pack(side=tk.LEFT, padx=2)

        # Category dropdown
        tk.Label(ff, text="Cat:", bg=COLORS["card"], fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._om_filter_cat = tk.OptionMenu(ff, self._filter_cat_var, "All")
        self._style_menu(self._om_filter_cat, width=10)
        self._om_filter_cat.pack(side=tk.LEFT, padx=2)

        # Search box
        self._search_entry = tk.Entry(ff, textvariable=self._filter_search_var,
                                      bg=COLORS["surface"], fg=COLORS["text"],
                                      insertbackground=COLORS["text"], font=FONT_SMALL, width=12)
        self._search_entry.pack(side=tk.LEFT, padx=4, ipady=2)

        # Reset button
        ttk.Button(ff, text="🔄 Reset", style="Accent.TButton",
                   command=self._reset_filters).pack(side=tk.LEFT, padx=2)

        self._filter_year_var.trace_add("write",   self._on_filter_changed)
        self._filter_month_var.trace_add("write",  self._on_filter_changed)
        self._filter_type_var.trace_add("write",   self._on_filter_type_changed)
        self._filter_cat_var.trace_add("write",    self._on_filter_changed)
        self._filter_search_var.trace_add("write", self._on_filter_changed)

        # Filter summary line
        self._filter_summary_lbl = tk.Label(
            lc, text="", bg=COLORS["card"], fg=COLORS["subtext"],
            font=("Segoe UI", 9, "italic"), anchor=tk.W
        )
        self._filter_summary_lbl.pack(fill=tk.X, padx=12, pady=(0, 4))

        cols = ("date", "type", "category", "amount", "note")
        self.tree = ttk.Treeview(lc, columns=cols,
                                 show="headings", selectmode="extended")
        for cid, head, w, anch in [
            ("date",     "Date & Time", 135, tk.CENTER),
            ("type",     "Type",         80, tk.CENTER),
            ("category", "Category",    120, tk.W),
            ("amount",   "Amount ($)",  125, tk.E),
            ("note",     "Note",        200, tk.W),
        ]:
            self.tree.heading(cid, text=head)
            self.tree.column(cid, width=w, anchor=anch)
        self.tree.tag_configure("income",  foreground=COLORS["green"])
        self.tree.tag_configure("expense", foreground=COLORS["red"])
        sb = ttk.Scrollbar(lc, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _style_menu(self, om: tk.OptionMenu, width: int = 6) -> None:
        """Helper to style ttk/tk OptionMenus consistently."""
        om.config(
            bg=COLORS["surface"], fg=COLORS["text"],
            activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
            relief=tk.FLAT, font=FONT_SMALL, bd=0, highlightthickness=0,
            width=width, cursor="hand2"
        )
        om["menu"].config(
            bg=COLORS["surface"], fg=COLORS["text"],
            activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
            font=FONT_SMALL
        )

    def _entry(self, parent, default: str = "") -> tk.Entry:
        e = tk.Entry(parent, bg=COLORS["surface"], fg=COLORS["text"],
                     insertbackground=COLORS["text"], font=FONT_BODY, relief=tk.FLAT)
        if default:
            e.insert(0, default)
        return e

    def _on_type_changed(self, *_args) -> None:
        tx_type = self._type_var.get()
        menu    = self._om_cat["menu"]
        menu.delete(0, "end")
        if tx_type == "Income":
            cats = self._income_cats
            self._cat_var.set("Salary")
            self._om_type.config(bg=COLORS["green"], activebackground=COLORS["green"])
        else:
            cats = self._expense_cats
            self._cat_var.set("Food")
            self._om_type.config(bg=COLORS["red"], activebackground=COLORS["red"])
        for c in cats:
            menu.add_command(label=c, command=lambda v=c: self._cat_var.set(v))

    def _on_filter_type_changed(self, *_args) -> None:
        """When filter type changes, update category filter options."""
        ttype = self._filter_type_var.get()
        cats = self.wallet.get_available_categories(tx_type=ttype if ttype != "All" else None)
        menu = self._om_filter_cat["menu"]
        menu.delete(0, "end")
        for it in ["All"] + cats:
            menu.add_command(label=it, command=lambda v=it: self._filter_cat_var.set(v))
        if self._filter_cat_var.get() not in ["All"] + cats:
            self._filter_cat_var.set("All")
        self._refresh_tree()

    def _on_filter_changed(self, *_args) -> None:
        yr  = self._filter_year_var.get()
        mon = self._filter_month_var.get()
        self._filter_year  = int(yr)  if yr  != "All" else None
        self._filter_month = int(mon) if mon != "All" else None
        self._refresh_tree()

    def _reset_filters(self) -> None:
        """Reset all filter controls to default."""
        self._filter_year_var.set("All")
        self._filter_month_var.set("All")
        self._filter_type_var.set("All")
        self._filter_cat_var.set("All")
        self._filter_search_var.set("")

    # ── Charts Tab ────────────────────────────────────────────────

    def _build_charts_tab(self) -> None:
        frame = self.tab_charts
        ctrl = tk.Frame(frame, bg=COLORS["bg"])
        ctrl.pack(fill=tk.X, padx=16, pady=(12, 4))

        tk.Label(ctrl, text="Chart:", bg=COLORS["bg"],
                 fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._chart_type_var = tk.StringVar(value=CHART_TYPES[0])
        self._chart_type_var.trace_add("write", lambda *_: self._schedule_chart_refresh())
        om_ct = tk.OptionMenu(ctrl, self._chart_type_var, *CHART_TYPES)
        om_ct.config(bg=COLORS["accent"], fg=COLORS["bg"],
                     activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
                     relief=tk.FLAT, font=FONT_BODY, bd=0, highlightthickness=0,
                     width=22, cursor="hand2")
        om_ct["menu"].config(bg=COLORS["surface"], fg=COLORS["text"],
                             activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
                             font=FONT_BODY)
        om_ct.pack(side=tk.LEFT, padx=(4, 20))

        tk.Label(ctrl, text="Year:", bg=COLORS["bg"],
                 fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._chart_year_var = tk.StringVar(value="All")
        self._chart_year_var.trace_add("write", lambda *_: self._schedule_chart_refresh())
        self._om_chart_year = tk.OptionMenu(ctrl, self._chart_year_var, "All")
        self._om_chart_year.config(
            bg=COLORS["surface"], fg=COLORS["text"],
            activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
            relief=tk.FLAT, font=FONT_SMALL, bd=0, highlightthickness=0,
            width=6, cursor="hand2")
        self._om_chart_year["menu"].config(
            bg=COLORS["surface"], fg=COLORS["text"],
            activebackground=COLORS["accent"], activeforeground=COLORS["bg"])
        self._om_chart_year.pack(side=tk.LEFT, padx=4)

        tk.Label(ctrl, text="Month:", bg=COLORS["bg"],
                 fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._chart_month_var = tk.StringVar(value="All")
        self._chart_month_var.trace_add("write", lambda *_: self._schedule_chart_refresh())
        self._om_chart_month = tk.OptionMenu(ctrl, self._chart_month_var, "All")
        self._om_chart_month.config(
            bg=COLORS["surface"], fg=COLORS["text"],
            activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
            relief=tk.FLAT, font=FONT_SMALL, bd=0, highlightthickness=0,
            width=4, cursor="hand2")
        self._om_chart_month["menu"].config(
            bg=COLORS["surface"], fg=COLORS["text"],
            activebackground=COLORS["accent"], activeforeground=COLORS["bg"])
        self._om_chart_month.pack(side=tk.LEFT, padx=4)

        self._chart_outer = tk.Frame(frame, bg=COLORS["card"])
        self._chart_outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        self._chart_area = tk.Frame(self._chart_outer, bg=COLORS["card"])
        self._chart_area.pack(fill=tk.BOTH, expand=True)

    # ── Budget Tab ────────────────────────────────────────────────

    def _build_budget_tab(self) -> None:
        frame = self.tab_budget
        left  = tk.Frame(frame, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.Y, padx=16, pady=16)
        right = tk.Frame(frame, bg=COLORS["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 16), pady=16)

        form = tk.Frame(left, bg=COLORS["card"])
        form.pack(fill=tk.X)
        tk.Label(form, text="🎯 Set Budget Limit", bg=COLORS["card"],
                 fg=COLORS["accent"], font=FONT_HEADER).grid(
            row=0, column=0, columnspan=2, padx=14, pady=(12, 8))
        tk.Label(form, text="Category:", bg=COLORS["card"],
                 fg=COLORS["subtext"], font=FONT_SMALL).grid(
            row=1, column=0, sticky=tk.W, padx=14, pady=4)

        _cats = ["Food", "Rent", "Transport", "Entertainment",
                 "Healthcare", "Education", "Utilities", "Shopping"]
        self._bgt_cat_var = tk.StringVar(value="Food")
        bom = tk.OptionMenu(form, self._bgt_cat_var, *_cats)
        bom.config(bg=COLORS["accent"], fg=COLORS["bg"],
                   activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
                   relief=tk.FLAT, font=FONT_BODY, bd=0, highlightthickness=0, cursor="hand2")
        bom["menu"].config(bg=COLORS["surface"], fg=COLORS["text"],
                           activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
                           font=FONT_BODY)
        bom.grid(row=1, column=1, sticky=tk.EW, padx=14, pady=4)

        tk.Label(form, text="Limit (USD):", bg=COLORS["card"],
                 fg=COLORS["subtext"], font=FONT_SMALL).grid(
            row=2, column=0, sticky=tk.W, padx=14, pady=4)
        self._bgt_amount = tk.Entry(form, bg=COLORS["surface"], fg=COLORS["text"],
                                    insertbackground=COLORS["text"],
                                    font=FONT_BODY, relief=tk.FLAT)
        self._bgt_amount.grid(row=2, column=1, sticky=tk.EW, padx=14, pady=4, ipady=4)
        form.columnconfigure(1, weight=1)
        ttk.Button(form, text="💾 Save Budget", style="Accent.TButton",
                   command=self.save_budget).grid(
            row=3, column=0, columnspan=2, padx=14, pady=12)

        ac = tk.Frame(right, bg=COLORS["card"])
        ac.pack(fill=tk.BOTH, expand=True)
        self._budget_title_lbl = tk.Label(ac, text="🚨 Budget Status (this month)",
                 bg=COLORS["card"], fg=COLORS["accent"], font=FONT_HEADER)
        self._budget_title_lbl.pack(padx=14, pady=(12, 6))
        self._budget_frame = tk.Frame(ac, bg=COLORS["card"])
        self._budget_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))

    # ── Refresh orchestration ─────────────────────────────────────

    def refresh_all(self) -> None:
        self._update_period_menus()
        self._refresh_stats()
        self._refresh_tree()
        self._refresh_budget_display()
        self._schedule_chart_refresh()

    def _schedule_chart_refresh(self) -> None:
        if not self._chart_pending:
            self._chart_pending = True
            self.after_idle(self._deferred_charts)

    def _deferred_charts(self) -> None:
        self._chart_pending = False
        cy = self._chart_year_var.get()  if hasattr(self, "_chart_year_var")  else "All"
        cm = self._chart_month_var.get() if hasattr(self, "_chart_month_var") else "All"
        self._chart_year  = int(cy) if cy  != "All" else None
        self._chart_month = int(cm) if cm  != "All" else None
        self._refresh_pie()
        self._refresh_timeline()
        self._refresh_active_chart()

    def _update_period_menus(self) -> None:
        years = self.wallet.get_analyzer().get_available_years()
        for om, var, items in [
            (self._om_filter_year,  self._filter_year_var,  ["All"] + [str(y) for y in years]),
            (self._om_filter_month, self._filter_month_var, ["All"] + [str(m) for m in range(1, 13)]),
        ]:
            menu = om["menu"]
            menu.delete(0, "end")
            for it in items:
                menu.add_command(label=it, command=lambda v=it, var=var: var.set(v))
        if hasattr(self, "_om_filter_cat"):
            ttype = self._filter_type_var.get() if hasattr(self, "_filter_type_var") else None
            cats = self.wallet.get_available_categories(tx_type=ttype if ttype != "All" else None)
            menu = self._om_filter_cat["menu"]
            menu.delete(0, "end")
            for it in ["All"] + cats:
                menu.add_command(label=it, command=lambda v=it: self._filter_cat_var.set(v))
        if hasattr(self, "_om_chart_year"):
            menu = self._om_chart_year["menu"]
            menu.delete(0, "end")
            for it in ["All"] + [str(y) for y in years]:
                menu.add_command(label=it,
                                 command=lambda v=it: self._chart_year_var.set(v))
        if hasattr(self, "_om_chart_month"):
            menu = self._om_chart_month["menu"]
            menu.delete(0, "end")
            for it in ["All"] + [str(m) for m in range(1, 13)]:
                menu.add_command(label=it,
                                 command=lambda v=it: self._chart_month_var.set(v))

    def _refresh_stats(self) -> None:
        stats = self.wallet.get_analyzer().get_summary_stats()
        bal   = stats["balance"]
        self._card_balance[1].config(text=_fmt(bal),
                                     style="Green.TLabel" if bal >= 0 else "Red.TLabel")
        self._card_income[1].config(text=_fmt(stats["total_income"]),   style="Green.TLabel")
        self._card_expense[1].config(text=_fmt(stats["total_expense"]), style="Red.TLabel")
        self._card_avg[1].config(text=_fmt(stats["avg_monthly_expense"]), style="Value.TLabel")

    def _refresh_tree(self) -> None:
        tree = self.tree
        tree.delete(*tree.get_children())
        
        yr = self._filter_year_var.get() if hasattr(self, "_filter_year_var") else "All"
        mon = self._filter_month_var.get() if hasattr(self, "_filter_month_var") else "All"
        ttype = self._filter_type_var.get() if hasattr(self, "_filter_type_var") else "All"
        cat = self._filter_cat_var.get() if hasattr(self, "_filter_cat_var") else "All"
        search = self._filter_search_var.get().strip() if hasattr(self, "_filter_search_var") else ""

        year_val = int(yr) if yr != "All" else None
        month_val = int(mon) if mon != "All" else None
        type_val = ttype if ttype != "All" else None
        cat_val = cat if cat != "All" else None

        df = self.wallet.filter_transactions(
            year=year_val, month=month_val, tx_type=type_val, category=cat_val, search=search
        )

        total_in = float(df[df["Type"] == "Income"]["Amount"].sum()) if not df.empty else 0.0
        total_ex = float(df[df["Type"] == "Expense"]["Amount"].sum()) if not df.empty else 0.0
        net = total_in - total_ex
        total_count = self.wallet.get_transaction_count()
        if hasattr(self, "_filter_summary_lbl"):
            self._filter_summary_lbl.config(
                text=f"Showing {len(df)} of {total_count} transactions | "
                     f"Income: +{_fmt(total_in)} | Expense: -{_fmt(total_ex)} | Net: {_fmt(net)}"
            )

        if df.empty:
            return

        rows = []
        for _, row in df.iterrows():
            tag = "income" if str(row.get("Type", "")) == "Income" else "expense"
            try:
                ts = pd.Timestamp(row["Date"])
                if ts.hour != 0 or ts.minute != 0 or ts.second != 0:
                    ds = ts.strftime("%Y-%m-%d %H:%M")
                else:
                    ds = ts.strftime("%Y-%m-%d")
            except Exception:
                ds = str(row["Date"])
            rows.append((ds,
                         "📥 In" if tag == "income" else "📤 Out",
                         row.get("Category", ""),
                         _fmt(float(row.get("Amount", 0))),
                         row.get("Note", ""),
                         tag))
        for r in rows:
            tree.insert("", tk.END, values=r[:5], tags=(r[5],))

    # ── Canvas management ─────────────────────────────────────────

    def _canvas(self, area: tk.Frame, fig_attr: str,
                canvas_attr: str, figsize: tuple) -> tuple:
        fig = getattr(self, fig_attr)
        cvs = getattr(self, canvas_attr)
        if fig is None or cvs is None:
            fig = Figure(figsize=figsize, facecolor=COLORS["card"])
            cvs = FigureCanvasTkAgg(fig, master=area)
            cvs.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            setattr(self, fig_attr,    fig)
            setattr(self, canvas_attr, cvs)
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_facecolor(COLORS["card"])
        return fig, ax

    def _no_data(self, ax, msg: str = "No data available") -> None:
        ax.text(0.5, 0.5, msg, ha="center", va="center",
                color=COLORS["subtext"], fontsize=12, transform=ax.transAxes)
        ax.axis("off")

    # ── Individual charts ─────────────────────────────────────────

    def _refresh_pie(self) -> None:
        fig, ax = self._canvas(self._pie_area, "_pie_fig", "_pie_canvas", (5, 3.5))
        data = self.wallet.get_analyzer().group_by_category("Expense")
        if data.empty:
            self._no_data(ax)
        else:
            wedges, texts, ats = ax.pie(
                data.values, labels=data.index,
                autopct="%1.1f%%", colors=COLORS["pie_colors"][:len(data)],
                startangle=90, pctdistance=0.82,
                wedgeprops=dict(linewidth=2, edgecolor=COLORS["card"]))
            for t  in texts: t.set_color(COLORS["text"]);   t.set_fontsize(8)
            for at in ats:   at.set_color(COLORS["bg"]);    at.set_fontsize(8); at.set_fontweight("bold")
            ax.legend(wedges, data.index, loc="lower center", bbox_to_anchor=(0.5, -0.22),
                      ncol=3, fontsize=7, facecolor=COLORS["surface"],
                      labelcolor=COLORS["text"], edgecolor=COLORS["border"])
        fig.tight_layout(pad=0.5)
        self._pie_canvas.draw_idle()

    def _refresh_timeline(self) -> None:
        fig, ax = self._canvas(self._tl_area, "_timeline_fig", "_timeline_canvas", (5, 3.5))
        tl = self.wallet.get_analyzer().get_balance_timeline()
        if tl.empty:
            self._no_data(ax)
        else:
            ax.plot(tl["Date"], tl["CumulativeBalance"],
                    color=COLORS["line"], linewidth=2.5, marker="o",
                    markersize=4, markerfacecolor=COLORS["accent"])
            ax.fill_between(tl["Date"], tl["CumulativeBalance"],
                            alpha=0.15, color=COLORS["line"])
            ax.axhline(0, color=COLORS["border"], linewidth=1, linestyle="--")
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_axis))
            ax.tick_params(colors=COLORS["subtext"], labelsize=7)
            ax.set_xlabel("Date",        color=COLORS["subtext"], fontsize=8)
            ax.set_ylabel("Balance (USD)", color=COLORS["subtext"], fontsize=8)
            for sp in ax.spines.values(): sp.set_color(COLORS["border"])
            fig.autofmt_xdate(rotation=30, ha="right")
        fig.tight_layout(pad=0.8)
        self._timeline_canvas.draw_idle()

    def _refresh_active_chart(self) -> None:
        ct = self._chart_type_var.get() if hasattr(self, "_chart_type_var") else CHART_TYPES[0]
        if ct == CHART_TYPES[0]:
            self._draw_bar_chart()
        elif ct == CHART_TYPES[1]:
            self._draw_correlation()
        elif ct == CHART_TYPES[2]:
            self._draw_kde()

    def _draw_bar_chart(self) -> None:
        fig, ax = self._canvas(self._chart_area, "_chart_fig", "_chart_canvas", (10, 4.5))
        labels, income, expense = self.wallet.get_analyzer().get_monthly_report_labels(
            year=self._chart_year)
        if not labels:
            self._no_data(ax, "No data for selected period")
        else:
            x = np.arange(len(labels)); w = 0.38
            bi = ax.bar(x - w/2, income,  width=w, color=COLORS["income_bar"],
                        label="Income", zorder=3)
            be = ax.bar(x + w/2, expense, width=w, color=COLORS["expense_bar"],
                        label="Expense", zorder=3)
            for bar in (*bi, *be):
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, h,
                            _fmt(h), ha="center", va="bottom",
                            color=COLORS["text"], fontsize=7, fontweight="bold")
            ax.set_xticks(x); ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_axis))
            ax.tick_params(colors=COLORS["subtext"])
            ax.set_ylabel("Amount (USD)", color=COLORS["subtext"], fontsize=9)
            ax.set_xlabel("Month",        color=COLORS["subtext"], fontsize=9)
            ax.legend(facecolor=COLORS["surface"], labelcolor=COLORS["text"],
                      edgecolor=COLORS["border"], fontsize=9)
            ax.grid(axis="y", color=COLORS["border"], linewidth=0.5,
                    linestyle="--", zorder=0)
            for sp in ax.spines.values(): sp.set_color(COLORS["border"])
        fig.tight_layout(pad=0.8)
        self._chart_canvas.draw_idle()

    def _draw_correlation(self) -> None:
        fig, ax = self._canvas(self._chart_area, "_chart_fig", "_chart_canvas", (8, 5))
        corr = self.wallet.get_analyzer().get_correlation_data(
            year=self._chart_year, month=self._chart_month)
        if corr.empty:
            self._no_data(ax, "Not enough data to compute correlation\n(need ≥ 2 categories, ≥ 4 rows)")
        else:
            import matplotlib.colors as mcolors
            cmap = mcolors.LinearSegmentedColormap.from_list(
                "custom", [COLORS["red"], COLORS["card"], COLORS["accent"]])
            im = ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
            fig.colorbar(im, ax=ax, shrink=0.8).ax.tick_params(
                colors=COLORS["subtext"], labelsize=8)
            cats = list(corr.columns)
            ax.set_xticks(range(len(cats))); ax.set_xticklabels(cats, rotation=45, ha="right",
                          color=COLORS["text"], fontsize=8)
            ax.set_yticks(range(len(cats))); ax.set_yticklabels(cats, color=COLORS["text"], fontsize=8)
            for i in range(len(cats)):
                for j in range(len(cats)):
                    ax.text(j, i, f"{corr.values[i,j]:.2f}",
                            ha="center", va="center",
                            color=COLORS["bg"] if abs(corr.values[i,j]) > 0.3 else COLORS["text"],
                            fontsize=8, fontweight="bold")
            ax.set_title("Correlation Matrix (Category Daily Totals)",
                         color=COLORS["text"], fontsize=10, pad=8)
            for sp in ax.spines.values(): sp.set_color(COLORS["border"])
        fig.tight_layout(pad=1.0)
        self._chart_canvas.draw_idle()

    def _draw_kde(self) -> None:
        fig = getattr(self, "_chart_fig")
        cvs = getattr(self, "_chart_canvas")
        if fig is None or cvs is None or not hasattr(self, "_kde_dual"):
            for w in self._chart_area.winfo_children():
                w.destroy()
            self._chart_canvas = None
            self._chart_fig    = None
            self._kde_dual     = True

        fig_attr, cvs_attr = "_chart_fig", "_chart_canvas"
        fig2 = getattr(self, fig_attr)
        cvs2 = getattr(self, cvs_attr)
        if fig2 is None or cvs2 is None:
            fig2 = Figure(figsize=(10, 4.5), facecolor=COLORS["card"])
            cvs2 = FigureCanvasTkAgg(fig2, master=self._chart_area)
            cvs2.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            setattr(self, fig_attr, fig2)
            setattr(self, cvs_attr, cvs2)
        fig2.clear()

        kde_data = self.wallet.get_analyzer().get_kde_data(
            year=self._chart_year, month=self._chart_month)

        axes_list = fig2.subplots(1, 2)
        for ax_sub in axes_list:
            ax_sub.set_facecolor(COLORS["card"])
            for sp in ax_sub.spines.values(): sp.set_color(COLORS["border"])

        pairs = [("expense", "Expense Distribution", COLORS["red"]),
                 ("income",  "Income Distribution",  COLORS["green"])]
        for ax_sub, (key, title, color) in zip(axes_list, pairs):
            d = kde_data.get(key)
            if not d:
                ax_sub.text(0.5, 0.5, f"No {key} data",
                            ha="center", va="center",
                            color=COLORS["subtext"], fontsize=11,
                            transform=ax_sub.transAxes)
                ax_sub.axis("off")
                continue
            edges = d["bin_edges"]
            widths = np.diff(edges)
            ax_sub.bar(edges[:-1], d["counts"], width=widths, align="edge",
                       color=color, alpha=0.45, edgecolor=COLORS["border"])
            if len(d["kde_x"]) > 0:
                ax2 = ax_sub.twinx()
                ax2.plot(d["kde_x"], d["kde_y"], color=color, linewidth=2.5)
                ax2.set_facecolor(COLORS["card"])
                ax2.tick_params(colors=COLORS["subtext"], labelsize=7)
                for sp in ax2.spines.values(): sp.set_color(COLORS["border"])
                ax2.set_ylabel("Density", color=COLORS["subtext"], fontsize=8)
            ax_sub.axvline(d["mean"],   color=COLORS["yellow"], linewidth=1.5,
                           linestyle="--", label=f'Mean {_fmt(d["mean"])}')
            ax_sub.axvline(d["median"], color=COLORS["accent"],  linewidth=1.5,
                           linestyle=":",  label=f'Median {_fmt(d["median"])}')
            ax_sub.set_title(title, color=COLORS["text"], fontsize=10)
            ax_sub.set_xlabel("Amount (USD)", color=COLORS["subtext"], fontsize=8)
            ax_sub.set_ylabel("Count",        color=COLORS["subtext"], fontsize=8)
            ax_sub.tick_params(colors=COLORS["subtext"], labelsize=7)
            ax_sub.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_axis))
            ax_sub.legend(facecolor=COLORS["surface"], labelcolor=COLORS["text"],
                          edgecolor=COLORS["border"], fontsize=8)
        fig2.tight_layout(pad=1.0)
        cvs2.draw_idle()

    def _refresh_budget_display(self) -> None:
        for w in self._budget_frame.winfo_children():
            w.destroy()
        alerts = self.wallet.get_budget_alerts()
        if hasattr(self, "_budget_title_lbl"):
            if alerts and "period" in alerts[0]:
                self._budget_title_lbl.config(text=f"🚨 Budget Status ({alerts[0]['period']})")
            else:
                self._budget_title_lbl.config(text="🚨 Budget Status (this month)")
        if not alerts:
            tk.Label(self._budget_frame,
                     text="No budget limits set.\nUse the form on the left.",
                     bg=COLORS["card"], fg=COLORS["subtext"],
                     font=FONT_BODY, justify=tk.CENTER).pack(pady=30)
            return
        for a in alerts:
            row  = tk.Frame(self._budget_frame, bg=COLORS["card"])
            row.pack(fill=tk.X, pady=4)
            over  = a["over"]
            color = COLORS["red"] if over else COLORS["green"]
            icon  = "🔴" if over else "🟢"
            tk.Label(row, text=f"{icon} {a['category']}",
                     bg=COLORS["card"], fg=color,
                     font=("Segoe UI", 10, "bold"),
                     width=18, anchor=tk.W).pack(side=tk.LEFT)
            bg_bar = tk.Frame(row, bg=COLORS["surface"], height=16)
            bg_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, ipady=2)
            bg_bar.pack_propagate(False)
            pct = min(a["percent"], 100)
            if pct > 0:
                tk.Frame(bg_bar, bg=COLORS["red"] if over else COLORS["accent"],
                         width=max(1, int(pct * 2))).pack(side=tk.LEFT, fill=tk.Y)
            warn = " ⚠️ OVER!" if over else ""
            tk.Label(row,
                     text=f"{_fmt(a['spent'])} / {_fmt(a['limit'])}  ({a['percent']:.1f}%){warn}",
                     bg=COLORS["card"], fg=COLORS["red"] if over else COLORS["subtext"],
                     font=FONT_SMALL, width=32, anchor=tk.W).pack(side=tk.LEFT)

    # ── Event handlers ────────────────────────────────────────────

    def add_transaction(self) -> None:
        date_s = self._entry_date.get().strip()
        ttype  = self._type_var.get()
        cat    = self._cat_var.get()
        amt_s  = self._entry_amount.get().strip().replace(",", "")
        note   = self._entry_note.get().strip()
        if not date_s or not cat or not amt_s:
            messagebox.showerror("Error", "Please fill in all required fields (*)")
            return
        try:
            self.wallet.add_transaction(date_s, cat, ttype, float(amt_s), note)
        except ValueError as exc:
            messagebox.showerror("Data Error", str(exc))
            return
        self._entry_amount.delete(0, tk.END)
        self._entry_note.delete(0, tk.END)
        self._entry_date.delete(0, tk.END)
        self._entry_date.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M"))
        self.refresh_all()
        messagebox.showinfo("Success", f"✅ Transaction added: {_fmt(float(amt_s))}")

    def delete_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Warning",
                                   "Please select at least one row\n(Ctrl+Click for multi-select)")
            return
        n = len(sel)
        if not messagebox.askyesno("Confirm", f"Delete {n} transaction(s)?"):
            return
        indices = sorted([self.tree.index(it) for it in sel], reverse=True)
        deleted, failed = self.wallet.delete_transactions_bulk(indices)
        self.refresh_all()
        if failed == 0:
            messagebox.showinfo("Success", f"✅ Deleted {deleted} transaction(s)")
        else:
            messagebox.showwarning("Partial", f"Deleted {deleted}/{n}. {failed} failed.")

    def delete_all(self) -> None:
        count = self.wallet.get_transaction_count()
        if count == 0:
            messagebox.showinfo("Info", "No transactions to delete.")
            return
        if not messagebox.askyesno(
            "⚠️ Confirm Delete All",
            f"Delete ALL {count} transactions?\n\nThis CANNOT be undone!\nA backup (.bak) will be created."
        ):
            return
        self._threaded(
            title="🗑 Deleting...",
            fn=self.wallet.delete_all_transactions,
            on_done=lambda n: messagebox.showinfo("Done", f"✅ Deleted all {n} transactions."),
            on_error=lambda e: messagebox.showerror("Error", str(e)),
        )

    def save_budget(self) -> None:
        cat  = self._bgt_cat_var.get()
        amt  = self._bgt_amount.get().strip().replace(",", "")
        if not cat or not amt:
            messagebox.showerror("Error", "Fill in all budget fields")
            return
        try:
            limit = float(amt)
        except ValueError:
            messagebox.showerror("Error", "Limit must be a number")
            return
        try:
            self.wallet.set_budget(cat, limit)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return
        self._bgt_amount.delete(0, tk.END)
        self._refresh_budget_display()
        messagebox.showinfo("Saved", f"✅ Budget set: {_fmt(limit)} for {cat}")

    def create_new_file(self) -> None:
        result = messagebox.askyesnocancel(
            "New File",
            "Create a new transaction file?\n\n"
            "YES    → Keep old file as backup\n"
            "NO     → Discard old data\n"
            "Cancel → Abort"
        )
        if result is None:
            return
        cur = Path(self.wallet._file_manager.file_path)
        if result:
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = cur.with_name(f"transactions_backup_{ts}.csv")
            shutil.copy2(cur, bak)
            msg = f"✅ Old data backed up as:\n{bak.name}"
        else:
            msg = "✅ New empty transaction file created."
        pd.DataFrame(columns=["Date", "Category", "Type", "Amount", "Note"]).to_csv(
            cur, index=False, encoding="utf-8-sig")
        self.wallet._file_manager.invalidate_cache()
        self.wallet.reload()
        self.refresh_all()
        messagebox.showinfo("Done", msg)

    # ── Threaded task helper ──────────────────────────────────────

    def _threaded(self, title: str, fn, on_done=None, on_error=None) -> None:
        prog = tk.Toplevel(self)
        prog.title(title); prog.geometry("380x140"); prog.resizable(False, False)
        prog.configure(bg=COLORS["bg"]); prog.grab_set()
        prog.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(prog, text=title, bg=COLORS["bg"],
                 fg=COLORS["accent"], font=FONT_HEADER).pack(pady=(18, 6))
        tk.Label(prog, text="Please wait…", bg=COLORS["bg"],
                 fg=COLORS["subtext"], font=FONT_SMALL).pack()
        bar = ttk.Progressbar(prog, mode="indeterminate", length=320,
                              style="Indeterminate.Horizontal.TProgressbar")
        bar.pack(pady=(10, 0)); bar.start(10)
        box: dict = {"value": None, "error": None}

        def worker():
            try:
                box["value"] = fn()
            except Exception as exc:
                box["error"] = exc
            self.after(0, _done)

        def _done():
            bar.stop(); prog.grab_release(); prog.destroy()
            self.refresh_all()
            if box["error"]:
                on_error and on_error(box["error"])
            else:
                on_done and on_done(box["value"])

        threading.Thread(target=worker, daemon=True).start()

    def import_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Excel file",
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")])
        if not path:
            return
        self._threaded(
            title="📂 Importing Excel…",
            fn=lambda: self.wallet.import_from_excel(path),
            on_done=lambda c: messagebox.showinfo("Done", f"✅ Imported {c} transactions"),
            on_error=lambda e: messagebox.showerror("Import Error", str(e)),
        )

    def import_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path:
            return
        self._threaded(
            title="📄 Importing CSV…",
            fn=lambda: self.wallet.import_from_csv(path),
            on_done=lambda c: messagebox.showinfo("Done", f"✅ Imported {c} transactions"),
            on_error=lambda e: messagebox.showerror("Import Error", str(e)),
        )

    def on_close(self) -> None:
        plt.close("all")
        self.destroy()


def main(data_file: str = "transactions.csv") -> None:
    app = SmartExpenseApp(data_file)
    app.mainloop()


if __name__ == "__main__":
    main()
