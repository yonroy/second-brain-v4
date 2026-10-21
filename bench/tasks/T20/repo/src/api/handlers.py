import functools

from src.tax import tax_rate

food_rate = functools.partial(tax_rate, "food")


def handle(req):
    return {"rate": food_rate()}
