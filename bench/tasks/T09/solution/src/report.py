import csv
from datetime import date


def rows():
    """Doanh thu theo đơn: ngày, khách hàng, số tiền (đồng)."""
    return [
        {"day": date(2026, 3, 5), "customer": "Nguyễn Văn An", "amount": 150000},
        {"day": date(2026, 3, 6), "customer": "Công ty Bình Minh, chi nhánh 2", "amount": 2750000},
        {"day": date(2026, 3, 7), "customer": "Đặng Thị Hoà", "amount": 99000},
    ]


def export_revenue_csv(path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        out = csv.writer(f, delimiter=";")
        out.writerow(["Ngày", "Khách hàng", "Số tiền"])
        for r in rows():
            out.writerow([r["day"].strftime("%d/%m/%Y"), r["customer"], r["amount"]])
