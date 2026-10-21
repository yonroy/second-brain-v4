from datetime import datetime, timezone


def stamp(dt: datetime) -> str:
    """Định dạng thời gian dùng chung."""
    return dt.astimezone(timezone.utc).strftime("%H:%M %d/%m/%Y")
