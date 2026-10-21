from datetime import datetime, timedelta

from src.timeutil import stamp


def eta(order_time: datetime, hours: int) -> datetime:
    return order_time + timedelta(hours=hours)


def log_line(order_time: datetime) -> str:
    return f"order at {stamp(order_time)}"
