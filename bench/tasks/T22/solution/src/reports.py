from collections import defaultdict
from datetime import timedelta


def daily_totals(rows):
    """rows: [{"day": date, "amount": int}] -> {"YYYY-MM-DD": tổng}"""
    out = defaultdict(int)
    for r in rows:
        out[r["day"].isoformat()] += r["amount"]
    return dict(out)


def weekly_totals(rows):
    out = defaultdict(int)
    for r in rows:
        start = r["day"] - timedelta(days=(r["day"].weekday() + 1) % 7)  # back to Sunday
        out[start.isoformat()] += r["amount"]
    return dict(out)
