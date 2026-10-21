from src import tax


def make(item):
    return {"tax": round(item["price"] * tax.tax_rate(item["cat"]))}
