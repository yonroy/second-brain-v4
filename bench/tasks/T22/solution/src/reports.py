from collections import defaultdict


def daily_totals(rows):
    """rows: [{"day": date, "amount": int}] -> {"YYYY-MM-DD": tổng}"""
    out = defaultdict(int)
    for r in rows:
        out[r["day"].isoformat()] += r["amount"]
    return dict(out)


def weekly_totals(rows):
    out = defaultdict(int)
    for r in rows:
        y, w, _ = r["day"].isocalendar()
        out[f"{y}-W{w:02d}"] += r["amount"]
    return dict(out)
