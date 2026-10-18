# -*- coding: utf-8 -*-
"""
src/ui/app_gui.py
=================
Tầng Giao diện: Tkinter GUI cho Smart Expense Manager.

Các tab:
  - Dashboard   : thẻ tổng quan + biểu đồ tròn + xu hướng số dư
  - Transactions: form nhập + bảng lịch sử với lọc tháng/năm
  - Charts      : biểu đồ cột, tương quan, mật độ KDE
                  with chart-type selector + period filter
  - Budget      : đặt hạn mức + thanh cảnh báo

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

# Chart type options for the Charts tab
CHART_TYPES: list[str] = [
    "Biểu đồ cột (Theo tháng)",
    "Tương quan danh mục",
    "Mật độ phân phối (KDE)",
]


def _fmt(amount: float) -> str:
    """Format a VND amount with thousands separator."""
    return f"{amount:,.0f} ₫"


def _fmt_axis_vi(value: float, _pos=None) -> str:
    """Smart axis formatter for VND amounts."""
    abs_v = abs(value)
    sign = "-" if value < 0 else ""
    if abs_v >= 1_000_000_000:
        return f"{sign}{abs_v/1e9:.1f}B ₫"
    elif abs_v >= 1_000_000:
        return f"{sign}{abs_v/1e6:.1f}M ₫"
    elif abs_v >= 1_000:
        return f"{sign}{abs_v/1e3:.0f}K ₫"
    else:
        return f"{sign}{abs_v:.0f} ₫"


class SmartExpenseApp(tk.Tk):
    """
    Main application window for Smart Expense Manager.

    Inherits from tk.Tk and manages the full application lifecycle.

    Attributes:
        wallet          : Business-layer facade.
        _chart_pending  : Debounce flag for deferred chart refresh.
        _*_fig / _canvas: Persistent Figure/Canvas pairs per chart area.
    """

    def __init__(self, data_file: str = "transactions.csv") -> None:
        """
        Initialise the app.

        Args:
            data_file: Path to the CSV transaction file.
        """
        super().__init__()
        self.wallet: Wallet = Wallet(data_file)

        # Persistent canvas references (reused, never recreated)
        self._pie_canvas:      Optional[FigureCanvasTkAgg] = None
        self._timeline_canvas: Optional[FigureCanvasTkAgg] = None
        self._chart_canvas:    Optional[FigureCanvasTkAgg] = None
        self._pie_fig:         Optional[Figure] = None
        self._timeline_fig:    Optional[Figure] = None
        self._chart_fig:       Optional[Figure] = None

        # Period filter state
        self._filter_year:  Optional[int] = None   # None = all
        self._filter_month: Optional[int] = None   # None = all

        # Chart tab state
        self._chart_year:  Optional[int] = None
        self._chart_month: Optional[int] = None

        self._chart_pending: bool = False

        self._setup_window()
        self._apply_theme()
        self._build_ui()
        self.refresh_all()

    # ── Window ────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        """Configure the root window."""
        self.title("💰 Smart Expense Manager")
        self.geometry("1340x820")
        self.minsize(1024, 680)
        self.configure(bg=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _apply_theme(self) -> None:
        """Apply dark Catppuccin theme to all ttk widgets."""
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

    # ── Build UI ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Assemble header, notebook, and all tab contents."""
        # Header
        hdr = tk.Frame(self, bg=COLORS["surface"], height=60)
        hdr.pack(fill=tk.X, side=tk.TOP)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="💰 Smart Expense Manager", font=FONT_TITLE,
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(side=tk.LEFT, padx=20, pady=12)
        self._lbl_clock = tk.Label(hdr, text="", font=FONT_SMALL,
                                   bg=COLORS["surface"], fg=COLORS["subtext"])
        self._lbl_clock.pack(side=tk.RIGHT, padx=20)
        self._tick()

        # Notebook
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tab_dash   = ttk.Frame(nb)
        self.tab_input  = ttk.Frame(nb)
        self.tab_charts = ttk.Frame(nb)
        self.tab_budget = ttk.Frame(nb)
        nb.add(self.tab_dash,   text="📊  Tổng quan")
        nb.add(self.tab_input,  text="➕  Nhập dữ liệu")
        nb.add(self.tab_charts, text="📈  Biểu đồ")
        nb.add(self.tab_budget, text="🎯  Ngân sách")

        self._build_dashboard()
        self._build_input_tab()
        self._build_charts_tab()
        self._build_budget_tab()

    def _tick(self) -> None:
        self._lbl_clock.config(text=datetime.now().strftime("%d/%m/%Y  %H:%M:%S"))
        self.after(1000, self._tick)

    # ── Dashboard ─────────────────────────────────────────────────

    def _build_dashboard(self) -> None:
        frame = self.tab_dash
        # Stat cards
        cf = tk.Frame(frame, bg=COLORS["bg"])
        cf.pack(fill=tk.X, padx=16, pady=16)
        self._card_balance = self._stat_card(cf, "💰 Số dư hiện tại",       "0 ₫", "Value.TLabel")
        self._card_income  = self._stat_card(cf, "📥 Tổng Thu",  "0 ₫", "Green.TLabel")
        self._card_expense = self._stat_card(cf, "📤 Tổng Chi", "0 ₫", "Red.TLabel")
        self._card_avg     = self._stat_card(cf, "📅 Chi TB/tháng",     "0 ₫", "Value.TLabel")
        for c, _ in [self._card_balance, self._card_income,
                     self._card_expense, self._card_avg]:
            c.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=6)
        # Charts row
        cr = tk.Frame(frame, bg=COLORS["bg"])
        cr.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        # Pie
        self._pie_frame = tk.Frame(cr, bg=COLORS["card"])
        self._pie_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        tk.Label(self._pie_frame, text="🥧 Cơ cấu Chi tiêu",
                 bg=COLORS["card"], fg=COLORS["accent"], font=FONT_HEADER).pack(pady=(10, 0))
        self._pie_area = tk.Frame(self._pie_frame, bg=COLORS["card"])
        self._pie_area.pack(fill=tk.BOTH, expand=True)
        # Timeline
        self._tl_frame = tk.Frame(cr, bg=COLORS["card"])
        self._tl_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(self._tl_frame, text="📈 Xu hướng Số dư",
                 bg=COLORS["card"], fg=COLORS["accent"], font=FONT_HEADER).pack(pady=(10, 0))
        self._tl_area = tk.Frame(self._tl_frame, bg=COLORS["card"])
        self._tl_area.pack(fill=tk.BOTH, expand=True)

    def _stat_card(self, parent, title: str, value: str, style: str) -> tuple:
        """Create a summary stat card widget.

        Args:
            parent: Parent widget.
            title:  Card label text.
            value:  Initial value string.
            style:  ttk style name for the value label.

        Returns:
            (card_frame, value_label) tuple.
        """
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

        # ── Add form ──
        fc = tk.Frame(left, bg=COLORS["card"])
        fc.pack(fill=tk.X)
        tk.Label(fc, text="➕ Thêm Giao dịch Mới", bg=COLORS["card"],
                 fg=COLORS["accent"], font=FONT_HEADER).grid(
            row=0, column=0, columnspan=2, padx=16, pady=(14, 10))

        self._entry_date = self._entry(fc, datetime.now().strftime("%d/%m/%Y %H:%M"))

        self._income_cats  = ["Lương", "Thưởng", "Lộc / Lì xì", "Đầu tư", "Kinh doanh", "Tiết kiệm", "Thu nhập khác"]
        self._expense_cats = ["Ăn uống", "Nhà cửa", "Di chuyển", "Mua sắm", "Học phí", "Y tế", "Giải trí", "Tiện ích", "Khác"]

        self._type_var = tk.StringVar(value="Chi tiêu")
        self._type_var.trace_add("write", self._on_type_changed)
        self._om_type = tk.OptionMenu(fc, self._type_var, "Chi tiêu", "Thu nhập")
        self._om_type.config(bg=COLORS["red"], fg=COLORS["bg"],
                             activebackground=COLORS["red"], activeforeground=COLORS["bg"],
                             relief=tk.FLAT, font=FONT_BODY, bd=0, highlightthickness=0,
                             cursor="hand2")
        self._om_type["menu"].config(bg=COLORS["surface"], fg=COLORS["text"],
                                     activebackground=COLORS["accent"],
                                     activeforeground=COLORS["bg"], font=FONT_BODY)

        self._cat_var = tk.StringVar(value="Ăn uống")
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
            ("Ngày & giờ (DD/MM/YYYY HH:MM) *", self._entry_date),
            ("Loại giao dịch *",               self._om_type),
            ("Danh mục *",                       self._om_cat),
            ("Số tiền (VNĐ) *",                   self._entry_amount),
            ("Ghi chú",                             self._entry_note),
        ]
        for i, (lbl, w) in enumerate(fields, start=1):
            tk.Label(fc, text=lbl, bg=COLORS["card"], fg=COLORS["subtext"],
                     font=FONT_SMALL).grid(row=i, column=0, sticky=tk.W, padx=16, pady=4)
            w.grid(row=i, column=1, sticky=tk.EW, padx=16, pady=4, ipady=4)
        fc.columnconfigure(1, weight=1)

        bf = tk.Frame(fc, bg=COLORS["card"])
        bf.grid(row=len(fields)+1, column=0, columnspan=2, padx=16, pady=14)
        for txt, cmd, pad in [
            ("✅ Thêm",         self.add_transaction,  (0, 8)),
            ("📂 Import Excel", self.import_excel,    (0, 8)),
            ("📄 Import CSV",   self.import_csv,      (0, 8)),
            ("📁 Tạo File Mới",     self.create_new_file, (0, 0)),
        ]:
            ttk.Button(bf, text=txt, style="Accent.TButton",
                       command=cmd).pack(side=tk.LEFT, padx=pad)

        # ── Transaction history list ──
        lc = tk.Frame(right, bg=COLORS["card"])
        lc.pack(fill=tk.BOTH, expand=True)

        hf = tk.Frame(lc, bg=COLORS["card"])
        hf.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(hf, text="📋 Lịch sử Giao dịch", bg=COLORS["card"],
                 fg=COLORS["accent"], font=FONT_HEADER).pack(side=tk.LEFT)
        ttk.Button(hf, text="🗑 Xóa tất cả",
                   style="Danger.TButton", command=self.delete_all).pack(
            side=tk.RIGHT, padx=(4, 0))
        ttk.Button(hf, text="🗑 Xóa đã chọn",
                   style="Danger.TButton", command=self.delete_selected).pack(
            side=tk.RIGHT)
        tk.Label(hf, text="Ctrl+Click để chọn nhiều",
                 bg=COLORS["card"], fg=COLORS["subtext"],
                 font=FONT_SMALL).pack(side=tk.RIGHT, padx=(0, 8))

        # ── Comprehensive Filter Bar (Bộ lọc - Lọc) ──
        ff = tk.Frame(lc, bg=COLORS["card"])
        ff.pack(fill=tk.X, padx=12, pady=(0, 2))

        tk.Label(ff, text="Bộ lọc:", bg=COLORS["card"],
                 fg=COLORS["accent"], font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))

        self._filter_year_var   = tk.StringVar(value="All")
        self._filter_month_var  = tk.StringVar(value="All")
        self._filter_type_var   = tk.StringVar(value="All")
        self._filter_cat_var    = tk.StringVar(value="All")
        self._filter_search_var = tk.StringVar(value="")

        # Năm
        tk.Label(ff, text="Năm:", bg=COLORS["card"], fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._om_filter_year = tk.OptionMenu(ff, self._filter_year_var, "All")
        self._style_menu(self._om_filter_year, width=5)
        self._om_filter_year.pack(side=tk.LEFT, padx=2)

        # Tháng
        tk.Label(ff, text="Tháng:", bg=COLORS["card"], fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._om_filter_month = tk.OptionMenu(ff, self._filter_month_var, "All")
        self._style_menu(self._om_filter_month, width=4)
        self._om_filter_month.pack(side=tk.LEFT, padx=2)

        # Loại
        tk.Label(ff, text="Loại:", bg=COLORS["card"], fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._om_filter_type = tk.OptionMenu(ff, self._filter_type_var, "All", "Thu nhập", "Chi tiêu")
        self._style_menu(self._om_filter_type, width=8)
        self._om_filter_type.pack(side=tk.LEFT, padx=2)

        # Danh mục
        tk.Label(ff, text="Danh mục:", bg=COLORS["card"], fg=COLORS["subtext"], font=FONT_SMALL).pack(side=tk.LEFT)
        self._om_filter_cat = tk.OptionMenu(ff, self._filter_cat_var, "All")
        self._style_menu(self._om_filter_cat, width=10)
        self._om_filter_cat.pack(side=tk.LEFT, padx=2)

        # Ô tìm kiếm
        self._search_entry = tk.Entry(ff, textvariable=self._filter_search_var,
                                      bg=COLORS["surface"], fg=COLORS["text"],
                                      insertbackground=COLORS["text"], font=FONT_SMALL, width=12)
        self._search_entry.pack(side=tk.LEFT, padx=4, ipady=2)

        # Nút đặt lại bộ lọc
        ttk.Button(ff, text="🔄 Đặt lại", style="Accent.TButton",
                   command=self._reset_filters).pack(side=tk.LEFT, padx=2)

        self._filter_year_var.trace_add("write",   self._on_filter_changed)
        self._filter_month_var.trace_add("write",  self._on_filter_changed)
        self._filter_type_var.trace_add("write",   self._on_filter_type_changed)
        self._filter_cat_var.trace_add("write",    self._on_filter_changed)
        self._filter_search_var.trace_add("write", self._on_filter_changed)

        # Dòng tóm tắt kết quả lọc
        self._filter_summary_lbl = tk.Label(
            lc, text="", bg=COLORS["card"], fg=COLORS["subtext"],
            font=("Segoe UI", 9, "italic"), anchor=tk.W
        )
        self._filter_summary_lbl.pack(fill=tk.X, padx=12, pady=(0, 4))

        # ── Treeview ──
        cols = ("date", "type", "category", "amount", "note")
        self.tree = ttk.Treeview(lc, columns=cols,
                                 show="headings", selectmode="extended")
        for cid, head, w, anch in [
            ("date",     "Ngày & Giờ",   135, "center"),
            ("type",     "Loại",          80, "center"),
            ("category", "Danh mục",     120, "center"),
            ("amount",   "Số tiền (VNĐ)", 135, "e"),
            ("note",     "Ghi chú",       200, "w"),
        ]:
            self.tree.heading(cid, text=head)
            self.tree.column(cid, width=w, anchor=anch)
        self.tree.tag_configure("income",  foreground=COLORS["green"])
        self.tree.tag_configure("expense", foreground=COLORS["red"])
        vsb = ttk.Scrollbar(lc, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        vsb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4))

    def _style_menu(self, om: tk.OptionMenu, width: int = 6) -> None:
        """Định dạng thống nhất cho OptionMenu."""
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
        """Create a styled Entry widget.

        Args:
            parent:  Parent widget.
            default: Pre-filled text.

        Returns:
            The Entry widget.
        """
        e = tk.Entry(parent, bg=COLORS["surface"], fg=COLORS["text"],
                     insertbackground=COLORS["text"], font=FONT_BODY, relief=tk.FLAT)
        if default:
            e.insert(0, default)
        return e

    def _on_type_changed(self, *_args) -> None:
        """Update category menu and button colour when type changes."""
        tx_type = self._type_var.get()
        menu    = self._om_cat["menu"]
        menu.delete(0, "end")
        if tx_type == "Thu nhập":
            cats = self._income_cats
            self._cat_var.set("Lương")
            self._om_type.config(bg=COLORS["green"], activebackground=COLORS["green"])
        else:
            cats = self._expense_cats
            self._cat_var.set("Ăn uống")
            self._om_type.config(bg=COLORS["red"], activebackground=COLORS["red"])
        for c in cats:
            menu.add_command(label=c, command=lambda v=c: self._cat_var.set(v))

    def _on_filter_type_changed(self, *_args) -> None:
        """Khi loại giao dịch lọc thay đổi, cập nhật danh sách danh mục tương ứng."""
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
        """Re-render the tree when the period filter changes."""
        yr  = self._filter_year_var.get()
        mon = self._filter_month_var.get()
        self._filter_year  = int(yr)  if yr  != "All" else None
        self._filter_month = int(mon) if mon != "All" else None
        self._refresh_tree()

    def _reset_filters(self) -> None:
        """Đặt lại toàn bộ bộ lọc về trạng thái ban đầu."""
        self._filter_year_var.set("All")
        self._filter_month_var.set("All")
        self._filter_type_var.set("All")
        self._filter_cat_var.set("All")
        self._filter_search_var.set("")

    # ── Charts Tab ────────────────────────────────────────────────

    def _build_charts_tab(self) -> None:
        frame = self.tab_charts

        # Controls bar
        ctrl = tk.Frame(frame, bg=COLORS["bg"])
        ctrl.pack(fill=tk.X, padx=16, pady=(12, 4))

        # Chart type selector
        tk.Label(ctrl, text="Biểu đồ:", bg=COLORS["bg"],
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

        # Period selectors for chart
        tk.Label(ctrl, text="Năm:", bg=COLORS["bg"],
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

        tk.Label(ctrl, text="Tháng:", bg=COLORS["bg"],
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

        # Chart canvas area
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
        tk.Label(form, text="🎯 Đặt Hạn mức Ngân sách", bg=COLORS["card"],
                 fg=COLORS["accent"], font=FONT_HEADER).grid(
            row=0, column=0, columnspan=2, padx=14, pady=(12, 8))
        tk.Label(form, text="Danh mục:", bg=COLORS["card"],
                 fg=COLORS["subtext"], font=FONT_SMALL).grid(
            row=1, column=0, sticky=tk.W, padx=14, pady=4)

        _cats = ["Ăn uống", "Nhà cửa", "Di chuyển", "Mua sắm", "Học phí", "Y tế", "Giải trí", "Tiện ích", "Khác"]
        self._bgt_cat_var = tk.StringVar(value="Ăn uống")
        bom = tk.OptionMenu(form, self._bgt_cat_var, *_cats)
        bom.config(bg=COLORS["accent"], fg=COLORS["bg"],
                   activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
                   relief=tk.FLAT, font=FONT_BODY, bd=0, highlightthickness=0, cursor="hand2")
        bom["menu"].config(bg=COLORS["surface"], fg=COLORS["text"],
                           activebackground=COLORS["accent"], activeforeground=COLORS["bg"],
                           font=FONT_BODY)
        bom.grid(row=1, column=1, sticky=tk.EW, padx=14, pady=4)

        tk.Label(form, text="Hạn mức (VNĐ):", bg=COLORS["card"],
                 fg=COLORS["subtext"], font=FONT_SMALL).grid(
            row=2, column=0, sticky=tk.W, padx=14, pady=4)
        self._bgt_amount = tk.Entry(form, bg=COLORS["surface"], fg=COLORS["text"],
                                    insertbackground=COLORS["text"],
                                    font=FONT_BODY, relief=tk.FLAT)
        self._bgt_amount.grid(row=2, column=1, sticky=tk.EW, padx=14, pady=4, ipady=4)
        form.columnconfigure(1, weight=1)
        ttk.Button(form, text="💾 Lưu Ngân sách", style="Accent.TButton",
                   command=self.save_budget).grid(
            row=3, column=0, columnspan=2, padx=14, pady=12)

        ac = tk.Frame(right, bg=COLORS["card"])
        ac.pack(fill=tk.BOTH, expand=True)
        self._budget_title_lbl = tk.Label(ac, text="🚨 Trạng thái Ngân sách Tháng này",
                 bg=COLORS["card"], fg=COLORS["accent"], font=FONT_HEADER)
        self._budget_title_lbl.pack(padx=14, pady=(12, 6))
        self._budget_frame = tk.Frame(ac, bg=COLORS["card"])
        self._budget_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))

    # ── Refresh orchestration ─────────────────────────────────────

    def refresh_all(self) -> None:
        """
        Full UI refresh — fast path (stats + tree) immediately,
        charts deferred via after_idle to avoid blocking the event loop.
        """
        self._update_period_menus()
        self._refresh_stats()
        self._refresh_tree()
        self._refresh_budget_display()
        self._schedule_chart_refresh()

    def _schedule_chart_refresh(self) -> None:
        """Schedule chart redraw once; debounce multiple rapid calls."""
        if not self._chart_pending:
            self._chart_pending = True
            self.after_idle(self._deferred_charts)

    def _deferred_charts(self) -> None:
        """Render all charts — called only when Tkinter is idle."""
        self._chart_pending = False
        cy = self._chart_year_var.get()  if hasattr(self, "_chart_year_var")  else "All"
        cm = self._chart_month_var.get() if hasattr(self, "_chart_month_var") else "All"
        self._chart_year  = int(cy) if cy  != "All" else None
        self._chart_month = int(cm) if cm  != "All" else None

        self._refresh_pie()
        self._refresh_timeline()
        self._refresh_active_chart()

    def _update_period_menus(self) -> None:
        """Populate year/month/category dropdowns from available data."""
        years  = self.wallet.get_analyzer().get_available_years()

        # --- Transaction filter menus ---
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

        # --- Chart period menus ---
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
        """Update 4 stat cards from current wallet data."""
        stats = self.wallet.get_analyzer().get_summary_stats()
        bal   = stats["balance"]
        self._card_balance[1].config(text=_fmt(bal),
                                     style="Green.TLabel" if bal >= 0 else "Red.TLabel")
        self._card_income[1].config(text=_fmt(stats["total_income"]),   style="Green.TLabel")
        self._card_expense[1].config(text=_fmt(stats["total_expense"]), style="Red.TLabel")
        self._card_avg[1].config(text=_fmt(stats["avg_monthly_expense"]), style="Value.TLabel")

    def _refresh_tree(self) -> None:
        """
        Repopulate the Treeview with multi-criteria filtered transactions.
        """
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
                text=f"Hiển thị {len(df)}/{total_count} giao dịch | "
                     f"Thu: +{_fmt(total_in)} | Chi: -{_fmt(total_ex)} | Chênh lệch: {_fmt(net)}"
            )

        if df.empty:
            return

        rows = []
        for _, row in df.iterrows():
            tag = "income" if str(row.get("Type", "")) == "Income" else "expense"
            try:
                ts = pd.Timestamp(row["Date"])
                if ts.hour != 0 or ts.minute != 0 or ts.second != 0:
                    ds = ts.strftime("%d/%m/%Y %H:%M")
                else:
                    ds = ts.strftime("%d/%m/%Y")
            except Exception:
                ds = str(row["Date"])
            rows.append((ds,
                         "📥 Thu" if tag == "income" else "📤 Chi",
                         row.get("Category", ""),
                         _fmt(float(row.get("Amount", 0))),
                         row.get("Note", ""),
                         tag))
        for r in rows:
            tree.insert("", tk.END, values=r[:5], tags=(r[5],))

    # ── Canvas management ─────────────────────────────────────────

    def _canvas(self, area: tk.Frame, fig_attr: str,
                canvas_attr: str, figsize: tuple) -> tuple:
        """
        Get or create a persistent (Figure, Axes) pair.

        On first call: creates Figure + FigureCanvasTkAgg and packs it.
        On subsequent calls: clears the figure and adds a fresh Axes.

        Args:
            area:        Container frame for the canvas widget.
            fig_attr:    Instance attribute name storing the Figure.
            canvas_attr: Instance attribute name storing the Canvas.
            figsize:     (width, height) in inches.

        Returns:
            (Figure, Axes) tuple ready to draw on.
        """
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

    def _no_data(self, ax, msg: str = "Chưa có dữ liệu") -> None:
        """Draw a placeholder message on an empty axes."""
        ax.text(0.5, 0.5, msg, ha="center", va="center",
                color=COLORS["subtext"], fontsize=12, transform=ax.transAxes)
        ax.axis("off")

    # ── Individual charts ─────────────────────────────────────────

    def _refresh_pie(self) -> None:
        """Redraw expense pie chart on the Dashboard."""
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
        """Redraw cumulative balance line chart on the Dashboard."""
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
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_axis_vi))
            ax.tick_params(colors=COLORS["subtext"], labelsize=7)
            ax.set_xlabel("Ngày",    color=COLORS["subtext"], fontsize=8)
            ax.set_ylabel("Số dư", color=COLORS["subtext"], fontsize=8)
            for sp in ax.spines.values(): sp.set_color(COLORS["border"])
            fig.autofmt_xdate(rotation=30, ha="right")
        fig.tight_layout(pad=0.8)
        self._timeline_canvas.draw_idle()

    def _refresh_active_chart(self) -> None:
        """Dispatch to the selected chart type in the Charts tab."""
        ct = self._chart_type_var.get() if hasattr(self, "_chart_type_var") else CHART_TYPES[0]
        if ct == CHART_TYPES[0]:
            self._draw_bar_chart()
        elif ct == CHART_TYPES[1]:
            self._draw_correlation()
        elif ct == CHART_TYPES[2]:
            self._draw_kde()

    def _draw_bar_chart(self) -> None:
        """Monthly income vs expense bar chart with period filter."""
        fig, ax = self._canvas(self._chart_area, "_chart_fig", "_chart_canvas", (10, 4.5))
        labels, income, expense = self.wallet.get_analyzer().get_monthly_report_labels(
            year=self._chart_year)
        if not labels:
            self._no_data(ax, "Chưa có dữ liệu cho kỳ đã chọn")
        else:
            x = np.arange(len(labels)); w = 0.38
            bi = ax.bar(x - w/2, income,  width=w, color=COLORS["income_bar"],
                        label="Thu nhập", zorder=3)
            be = ax.bar(x + w/2, expense, width=w, color=COLORS["expense_bar"],
                        label="Chi tiêu", zorder=3)
            for bar in (*bi, *be):
                h = bar.get_height()
                if h > 0:
                    lbl = f"{h/1e9:.1f}B" if h >= 1e9 else (f"{h/1e6:.1f}M" if h >= 1e6 else (f"{h/1e3:.0f}K" if h >= 1e3 else f"{h:.0f}"))
                    ax.text(bar.get_x() + bar.get_width()/2, h,
                            lbl, ha="center", va="bottom",
                            color=COLORS["text"], fontsize=7, fontweight="bold")
            ax.set_xticks(x); ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_axis_vi))
            ax.tick_params(colors=COLORS["subtext"])
            ax.set_ylabel("Số tiền (VNĐ)", color=COLORS["subtext"], fontsize=9)
            ax.set_xlabel("Tháng",        color=COLORS["subtext"], fontsize=9)
            ax.legend(facecolor=COLORS["surface"], labelcolor=COLORS["text"],
                      edgecolor=COLORS["border"], fontsize=9)
            ax.grid(axis="y", color=COLORS["border"], linewidth=0.5,
                    linestyle="--", zorder=0)
            for sp in ax.spines.values(): sp.set_color(COLORS["border"])
        fig.tight_layout(pad=0.8)
        self._chart_canvas.draw_idle()

    def _draw_correlation(self) -> None:
        """Category-amount correlation heatmap."""
        fig, ax = self._canvas(self._chart_area, "_chart_fig", "_chart_canvas", (8, 5))
        corr = self.wallet.get_analyzer().get_correlation_data(
            year=self._chart_year, month=self._chart_month)
        if corr.empty:
            self._no_data(ax, "Không đủ dữ liệu tính tương quan\n(cần ≥ 2 danh mục, ≥ 4 hàng)")
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
            ax.set_title("Ma trận tương quan (Tổng ngày theo Danh mục)",
                         color=COLORS["text"], fontsize=10, pad=8)
            for sp in ax.spines.values(): sp.set_color(COLORS["border"])
        fig.tight_layout(pad=1.0)
        self._chart_canvas.draw_idle()

    def _draw_kde(self) -> None:
        """KDE density plot for expense and income distributions."""
        fig = getattr(self, "_chart_fig")
        cvs = getattr(self, "_chart_canvas")
        # Need 2 subplots — recreate if needed
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

        pairs = [("expense", "Phân phối Chi tiêu", COLORS["red"]),
                 ("income",  "Phân phối Thu nhập",  COLORS["green"])]
        for ax_sub, (key, title, color) in zip(axes_list, pairs):
            d = kde_data.get(key)
            if not d:
                label_vn = "chi tiêu" if key == "expense" else "thu nhập"
                ax_sub.text(0.5, 0.5, f"Chưa có dữ liệu {label_vn}",
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
                ax2.set_ylabel("Mật độ", color=COLORS["subtext"], fontsize=8)
            ax_sub.axvline(d["mean"],   color=COLORS["yellow"], linewidth=1.5,
                           linestyle="--", label=f'Trung bình {_fmt_axis_vi(d["mean"])}')
            ax_sub.axvline(d["median"], color=COLORS["accent"],  linewidth=1.5,
                           linestyle=":",  label=f'Trung vị {_fmt_axis_vi(d["median"])}')
            ax_sub.set_title(title, color=COLORS["text"], fontsize=10)
            ax_sub.set_xlabel("Số tiền (VNĐ)", color=COLORS["subtext"], fontsize=8)
            ax_sub.set_ylabel("Số lần",        color=COLORS["subtext"], fontsize=8)
            ax_sub.tick_params(colors=COLORS["subtext"], labelsize=7)
            ax_sub.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: _fmt_axis_vi(v)))
            ax_sub.legend(facecolor=COLORS["surface"], labelcolor=COLORS["text"],
                          edgecolor=COLORS["border"], fontsize=8)
        fig2.tight_layout(pad=1.0)
        cvs2.draw_idle()

    def _refresh_budget_display(self) -> None:
        """Rebuild the budget alert progress bars."""
        for w in self._budget_frame.winfo_children():
            w.destroy()
        alerts = self.wallet.get_budget_alerts()
        if hasattr(self, "_budget_title_lbl"):
            if alerts and "period" in alerts[0]:
                self._budget_title_lbl.config(text=f"🚨 Trạng thái Ngân sách (Tháng {alerts[0]['period']})")
            else:
                self._budget_title_lbl.config(text="🚨 Trạng thái Ngân sách Tháng này")
        if not alerts:
            tk.Label(self._budget_frame,
                     text="Chưa có hạn mức.\nDùng form bên trái để thêm.",
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
            warn = " ⚠️ VƯỢT!" if over else ""
            tk.Label(row,
                     text=f"{_fmt(a['spent'])} / {_fmt(a['limit'])}  ({a['percent']:.1f}%){warn}",
                     bg=COLORS["card"], fg=COLORS["red"] if over else COLORS["subtext"],
                     font=FONT_SMALL, width=32, anchor=tk.W).pack(side=tk.LEFT)

    # ── Event handlers ────────────────────────────────────────────

    def add_transaction(self) -> None:
        """Validate the form and add a new transaction."""
        date_s = self._entry_date.get().strip()
        ttype  = self._type_var.get()
        cat    = self._cat_var.get()
        amt_s  = self._entry_amount.get().strip().replace(",", "")
        note   = self._entry_note.get().strip()
        if not date_s or not cat or not amt_s:
            messagebox.showerror("Lỗi", "Vui lòng điền đầy đủ các trường bắt buộc (*)")
            return
        # Chuyển nhãn tiếng Việt sang giá trị nội bộ tiếng Anh
        ttype_internal = "Income" if ttype == "Thu nhập" else "Expense"
        try:
            self.wallet.add_transaction(date_s, cat, ttype_internal, float(amt_s), note)
        except ValueError as exc:
            messagebox.showerror("Lỗi dữ liệu", str(exc))
            return
        self._entry_amount.delete(0, tk.END)
        self._entry_note.delete(0, tk.END)
        self._entry_date.delete(0, tk.END)
        self._entry_date.insert(0, datetime.now().strftime("%d/%m/%Y %H:%M"))
        self.refresh_all()
        messagebox.showinfo("Thành công", f"✅ Đã thêm giao dịch {_fmt(float(amt_s))}")

    def delete_selected(self) -> None:
        """Bulk-delete selected rows (1 file write total)."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Chú ý",
                                   "Vui lòng chọn ít nhất một giao dịch\n(Giữ Ctrl để chọn nhiều)")
            return
        n = len(sel)
        if not messagebox.askyesno("Xác nhận",
                                   f"Xóa {n} giao dịch đã chọn?"):
            return
        indices = sorted([self.tree.index(it) for it in sel], reverse=True)
        deleted, failed = self.wallet.delete_transactions_bulk(indices)
        self.refresh_all()
        if failed == 0:
            messagebox.showinfo("Thành công", f"✅ Đã xóa {deleted} giao dịch")
        else:
            messagebox.showwarning("Một phần thành công", f"Xóa {deleted}/{n}. {failed} lỗi.")

    def delete_all(self) -> None:
        """Delete all transactions via threaded task with progress bar."""
        count = self.wallet.get_transaction_count()
        if count == 0:
            messagebox.showinfo("Thông báo", "Không có giao dịch nào để xóa.")
            return
        if not messagebox.askyesno(
            "⚠️ Xác nhận Xóa tất cả",
            f"Xóa TOÀN BỘ {count} giao dịch?\n\nKhông thể hoàn tác!\nFile backup (.bak) sẽ được tạo."
        ):
            return
        self._threaded(
            title="🗑 Đang xóa...",
            fn=self.wallet.delete_all_transactions,
            on_done=lambda n: messagebox.showinfo("Hoàn tất", f"✅ Đã xóa toàn bộ {n} giao dịch."),
            on_error=lambda e: messagebox.showerror("Lỗi", str(e)),
        )

    def save_budget(self) -> None:
        """Save a budget limit for the selected category."""
        cat  = self._bgt_cat_var.get()
        amt  = self._bgt_amount.get().strip().replace(",", "")
        if not cat or not amt:
            messagebox.showerror("Lỗi", "Vui lòng nhập đầy đủ thông tin ngân sách")
            return
        try:
            limit = float(amt)
        except ValueError:
            messagebox.showerror("Lỗi", "Hạn mức phải là số")
            return
        try:
            self.wallet.set_budget(cat, limit)
        except ValueError as exc:
            messagebox.showerror("Lỗi", str(exc))
            return
        self._bgt_amount.delete(0, tk.END)
        self._refresh_budget_display()
        messagebox.showinfo("Đã lưu", f"✅ Đã đặt {_fmt(limit)} cho {cat}")

    def create_new_file(self) -> None:
        """Reset transaction data to an empty CSV."""
        result = messagebox.askyesnocancel(
            "Tạo File Mới",
            "Tạo file giao dịch mới?\n\n"
            "CÓ    → Giữ file cũ làm backup\n"
            "KHÔNG → Xóa dữ liệu cũ\n"
            "Hủy  → Hủy thao tác"
        )
        if result is None:
            return
        cur = Path(self.wallet._file_manager.file_path)
        if result:
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = cur.with_name(f"transactions_backup_{ts}.csv")
            shutil.copy2(cur, bak)
            msg = f"✅ File cũ đã sao lưu:\n{bak.name}"
        else:
            msg = "✅ File giao dịch mới đã được tạo."
        pd.DataFrame(columns=["Date", "Category", "Type", "Amount", "Note"]).to_csv(
            cur, index=False, encoding="utf-8-sig")
        self.wallet._file_manager.invalidate_cache()
        self.wallet.reload()
        self.refresh_all()
        messagebox.showinfo("Hoàn tất", msg)

    # ── Threaded task helper ──────────────────────────────────────

    def _threaded(self, title: str, fn, on_done=None, on_error=None) -> None:
        """
        Run a blocking function in a daemon thread with a progress dialog.

        The progress dialog is modal (grab_set). UI remains responsive.
        refresh_all() is called on the main thread after completion.

        Args:
            title:    Window and label text.
            fn:       Callable → result  (runs in worker thread).
            on_done:  Callable(result)   (runs on main thread).
            on_error: Callable(exception)(runs on main thread).
        """
        prog = tk.Toplevel(self)
        prog.title(title); prog.geometry("380x140"); prog.resizable(False, False)
        prog.configure(bg=COLORS["bg"]); prog.grab_set()
        prog.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(prog, text=title, bg=COLORS["bg"],
                 fg=COLORS["accent"], font=FONT_HEADER).pack(pady=(18, 6))
        tk.Label(prog, text="Vui lòng chờ...", bg=COLORS["bg"],
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
        """Import transactions from an Excel file (threaded)."""
        path = filedialog.askopenfilename(
            title="Chọn file Excel ngân hàng",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All", "*.*")])
        if not path:
            return
        self._threaded(
            title="📂 Đang nhập Excel…",
            fn=lambda: self.wallet.import_from_excel(path),
            on_done=lambda c: messagebox.showinfo("Hoàn tất", f"✅ Đã import {c} giao dịch"),
            on_error=lambda e: messagebox.showerror("Lỗi import", str(e)),
        )

    def import_csv(self) -> None:
        """Import transactions from a CSV file (threaded)."""
        path = filedialog.askopenfilename(
            title="Chọn file CSV sao kê",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path:
            return
        self._threaded(
            title="📄 Đang nhập CSV…",
            fn=lambda: self.wallet.import_from_csv(path),
            on_done=lambda c: messagebox.showinfo("Hoàn tất", f"✅ Đã import {c} giao dịch"),
            on_error=lambda e: messagebox.showerror("Lỗi import", str(e)),
        )

    def on_close(self) -> None:
        """Cleanly close all matplotlib figures before destroying the window."""
        plt.close("all")
        self.destroy()


def main(data_file: str = "transactions.csv") -> None:
    """Entry point — create and run the app.

    Args:
        data_file: Path to the CSV transaction file.
    """
    app = SmartExpenseApp(data_file)
    app.mainloop()


if __name__ == "__main__":
    main()
