from collections import defaultdict


def daily_totals(rows):
    """rows: [{"day": date, "amount": int}] -> {"YYYY-MM-DD": tổng}"""
    out = defaultdict(int)
    for r in rows:
        out[r["day"].isoformat()] += r["amount"]
    return dict(out)
