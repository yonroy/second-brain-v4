from datetime import datetime, timedelta, timezone

from src.timeutil import stamp

VN = timezone(timedelta(hours=7))


def eta(order_time: datetime, hours: int) -> datetime:
    return order_time + timedelta(hours=hours)


def format_eta(order_time: datetime, hours: int) -> str:
    return eta(order_time, hours).astimezone(VN).strftime("%H:%M %d/%m/%Y")


def log_line(order_time: datetime) -> str:
    return f"order at {stamp(order_time)}"
