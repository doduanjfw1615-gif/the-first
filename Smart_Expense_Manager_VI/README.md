# Smart Expense Manager — Phiên bản Tiếng Việt

> Ứng dụng Desktop quản lý tài chính cá nhân — Python 3.10+  
> Kiến trúc: OOP · 3 tầng · Pandas · Matplotlib · Tkinter

---

## Tính năng

| # | Tính năng | Trạng thái |
|---|-----------|-----------|
| 1 | Thêm / Xóa giao dịch (Thu / Chi) | Hoàn thành |
| 2 | Validation dữ liệu (số tiền > 0, định dạng ngày) | Hoàn thành |
| 3 | Tự động tính số dư | Hoàn thành |
| 4 | Thống kê theo danh mục | Hoàn thành |
| 5 | Biểu đồ tròn — cơ cấu chi tiêu | Hoàn thành |
| 6 | Biểu đồ cột — thu chi theo tháng | Hoàn thành |
| 7 | Biểu đồ đường — xu hướng số dư | Hoàn thành |
| 8 | **Biểu đồ tương quan danh mục** (mới) | Hoàn thành |
| 9 | **Biểu đồ mật độ KDE** (mới) | Hoàn thành |
| 10 | **Lọc theo tháng / năm** trên lịch sử & biểu đồ (mới) | Hoàn thành |
| 11 | Import từ Excel (.xlsx / .xls) | Hoàn thành |
| 12 | Import từ CSV (tự nhận diện cột tiếng Việt/Anh) | Hoàn thành |
| 13 | Cảnh báo ngân sách với thanh đỏ | Hoàn thành |
| 14 | Xóa nhiều cùng lúc (1 lần ghi file, không lag) | Hoàn thành |
| 15 | Import/Xóa có thanh tiến độ, không not-responding | Hoàn thành |
| 16 | Tạo file giao dịch mới (có tùy chọn backup) | Hoàn thành |

---

## Khởi chạy nhanh

```bash
# 1. Cài thư viện
pip install pandas matplotlib openpyxl xlrd scipy

# 2. Chạy ứng dụng
python main.py
# hoặc dùng shortcut:
python run_vi.py
```

---

## Cấu trúc thư mục

```
Smart_Expense_Manager_VI/
├── main.py                    ← Điểm khởi chạy
├── run_vi.py                  ← Shortcut launcher
├── transactions.csv           ← File dữ liệu (tự tạo)
├── budgets.json               ← Hạn mức ngân sách (tự tạo)
├── sample_import.csv          ← CSV mẫu để test import
│
└── src/
    ├── models/
    │   └── transaction.py     ← Transaction ABC + Income/Expense + Factory
    ├── data/
    │   └── file_manager.py    ← Đọc/ghi CSV/Excel với cache
    ├── business/
    │   ├── wallet.py          ← Facade: CRUD + xóa bulk + import
    │   └── analyzer.py        ← Phân tích Pandas + lọc kỳ + KDE + tương quan
    └── ui/
        └── app_gui.py         ← Tkinter GUI (4 tab, canvas cố định)
```

---

## Định dạng CSV Import

Tên cột chuẩn (được nhận diện tự động):

```csv
Date,Category,Type,Amount,Note
2024-01-01,Salary,Income,20000000,Lương tháng 1
2024-01-02,Food,Expense,150000,Ăn trưa
```

Cũng hỗ trợ tên cột tiếng Việt:

| Cột chuẩn | Tên tiếng Việt được nhận diện |
|-----------|-------------------------------|
| Date | Ngày, Ngay, Transaction Date |
| Amount | Số Tiền, So Tien, Tien |
| Type | Loại, Loai, Trans Type |
| Category | Danh Mục, Danh Muc |
| Note | Ghi Chú, Ghi Chu, Description |

---

## Hướng dẫn sử dụng biểu đồ

| Biểu đồ | Mô tả | Lọc kỳ |
|---------|-------|---------|
| Biểu đồ cột (Theo tháng) | Thu nhập vs Chi tiêu từng tháng | Năm |
| Tương quan danh mục | Ma trận tương quan Pearson theo ngày | Năm + Tháng |
| Mật độ phân phối (KDE) | Phân phối số tiền giao dịch + mean/median | Năm + Tháng |

---

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────┐
│   Tầng Giao diện  (src/ui/)             │
│   SmartExpenseApp  ←  Tkinter + MPL     │
└──────────────┬──────────────────────────┘
               │ gọi API công khai
┌──────────────▼──────────────────────────┐
│   Tầng Nghiệp vụ  (src/business/)       │
│   Wallet (Facade)  ←→  FinancialAnalyzer│
└──────────────┬──────────────────────────┘
               │ đọc / ghi
┌──────────────▼──────────────────────────┐
│   Tầng Dữ liệu    (src/data/)           │
│   TransactionFileManager (CSV cache)    │
└─────────────────────────────────────────┘
```

### Nguyên tắc OOP áp dụng

| Nguyên tắc | Vị trí trong code |
|------------|------------------|
| **Trừu tượng** | `Transaction` là ABC — không thể khởi tạo trực tiếp |
| **Kế thừa** | `IncomeTransaction`, `ExpenseTransaction` kế thừa `Transaction` |
| **Đa hình** | `get_signed_amount()` trả +/- tùy lớp con |
| **Đóng gói** | `Wallet.__transactions` là private (name-mangled) |
| **Factory** | `TransactionFactory.create()` chọn đúng lớp con |
| **Facade** | `Wallet` ẩn FileManager + Analyzer với tầng UI |
| **Wrapper** | `FinancialAnalyzer` bọc DataFrame, cung cấp API sạch |

---

## Phím tắt

| Thao tác | Phím tắt |
|----------|---------|
| Chọn nhiều hàng | `Ctrl + Click` |

---

## Yêu cầu hệ thống

- Python 3.10 trở lên
- pandas ≥ 1.5
- matplotlib ≥ 3.5
- openpyxl (cho .xlsx)
- xlrd (cho .xls)
- scipy (cho biểu đồ KDE)

---

*Smart Expense Manager — Phiên bản Tiếng Việt*
