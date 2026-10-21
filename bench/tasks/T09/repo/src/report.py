from datetime import date


def rows():
    """Doanh thu theo đơn: ngày, khách hàng, số tiền (đồng)."""
    return [
        {"day": date(2026, 3, 5), "customer": "Nguyễn Văn An", "amount": 150000},
        {"day": date(2026, 3, 6), "customer": "Công ty Bình Minh, chi nhánh 2", "amount": 2750000},
        {"day": date(2026, 3, 7), "customer": "Đặng Thị Hoà", "amount": 99000},
    ]
