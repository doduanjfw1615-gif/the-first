# the-first
Hi, it just my idea about manage the personal finance, hope u enjoy this
# 💰 Smart Expense Manager — Bộ đôi bản Tiếng Anh & Tiếng Việt

> Ứng dụng Desktop quản lý tài chính cá nhân — Python 3.10+  
> Kiến trúc: OOP · 3 tầng · Pandas · Matplotlib · Tkinter

Repo này chứa **2 phiên bản cùng một ứng dụng**: giao diện **Tiếng Anh** và **Tiếng Việt**, mỗi bản là một thư mục độc lập, chạy được riêng, dữ liệu riêng.

---

## 📂 Các phiên bản

| Thư mục | Ngôn ngữ giao diện | File chạy nhanh |
|---------|-------------------|-----------------|
| `Smart_Expense_Manager_EN/` | Tiếng Anh | `SmartExpenseManager_EN.exe` |
| `Smart_Expense_Manager_VI/` | Tiếng Việt | `SmartExpenseManager_VI.exe` |

Chi tiết tính năng, kiến trúc, định dạng CSV import xem trong `README.md` của từng thư mục con.

---

## ✨ Tính năng chung

- Thêm / xóa giao dịch Thu / Chi, tự động tính số dư
- Thống kê theo danh mục, cảnh báo ngân sách với thanh đỏ
- Biểu đồ: tròn (cơ cấu chi), cột (thu chi theo tháng), đường (xu hướng số dư), **heatmap tương quan**, **mật độ KDE**
- Lọc lịch sử & biểu đồ theo tháng / năm
- Import CSV (tự nhận diện cột tiếng Việt/Anh) và Excel (.xlsx / .xls)
- Xóa nhiều dòng cùng lúc, import/xóa chạy luồng riêng có thanh tiến độ
- Tạo file dữ liệu mới (có tùy chọn backup)

---

## 🚀 Cách chạy

### Cách 1 — Double-click file exe (không cần cài gì)

```
Smart_Expense_Manager_EN\SmartExpenseManager_EN.exe
Smart_Expense_Manager_VI\SmartExpenseManager_VI.exe
```

Lưu ý:

- **Giữ nguyên exe ở trong thư mục project** (cạnh `transactions.csv`) — app đọc/ghi dữ liệu theo vị trí đó.
- Lần đầu mở chậm hơn vài giây (bản `--onefile` giải nén tạm); Windows SmartScreen có thể cảnh báo → chọn **More info → Run anyway**.
- Mỗi exe ~283MB vì đã gói sẵn Python + pandas + numpy + matplotlib.

### Cách 2 — Chạy bằng Python (khi dev / chỉnh sửa code)

```bash
# Vào thư mục bản muốn chạy, ví dụ bản EN:
cd Smart_Expense_Manager_EN

# Cài thư viện (lần đầu)
pip install pandas matplotlib openpyxl xlrd scipy

# Chạy app
python main.py
# hoặc shortcut:
python run_en.py        # bản VI: python run_vi.py
```

---

## 📁 Cấu trúc tổng thể

```
the-first-main/
├── README.md                          ← File này (tổng quan)
│
├── Smart_Expense_Manager_EN/          ← Bản Tiếng Anh
│   ├── SmartExpenseManager_EN.exe     ← Double-click để mở app
│   ├── main.py                        ← Điểm khởi chạy
│   ├── run_en.py                      ← Shortcut launcher
│   ├── transactions.csv               ← Dữ liệu giao dịch
│   ├── budgets.json                   ← Hạn mức ngân sách
│   └── src/                           ← models / data / business / ui
│
└── Smart_Expense_Manager_VI/          ← Bản Tiếng Việt (cấu trúc tương tự)
    ├── SmartExpenseManager_VI.exe
    ├── main.py
    ├── run_vi.py
    ├── transactions.csv
    ├── budgets.json
    └── src/
```

---

## 🛠 Yêu cầu (khi chạy bằng Python)

- Python 3.10 trở lên
- pandas ≥ 1.5 · matplotlib ≥ 3.5 · numpy
- openpyxl (cho .xlsx) · xlrd (cho .xls) · scipy (cho biểu đồ KDE)

Chạy bằng exe thì **không cần cài gì cả**.

---

## 🔁 Đóng gói lại exe (sau khi sửa code)

```bash
cd Smart_Expense_Manager_EN
python -m PyInstaller --onefile --noconsole --name SmartExpenseManager_EN run_en.py

cd Smart_Expense_Manager_VI
python -m PyInstaller --onefile --noconsole --name SmartExpenseManager_VI run_vi.py
```

Exe mới nằm trong `dist\` của từng thư mục — chép ra thư mục gốc (cạnh `transactions.csv`) rồi xóa `build/`, `dist/`, `*.spec`.

---

*Smart Expense Manager — English Edition & Phiên bản Tiếng Việt*
