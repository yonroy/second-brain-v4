from src.tax import tax_rate


def total(items):
    return sum(round(i["price"] * (1 + tax_rate(i["cat"]))) for i in items)
