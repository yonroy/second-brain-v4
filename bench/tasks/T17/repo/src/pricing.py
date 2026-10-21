from src import supplier


def get_price(sku):
    return supplier.fetch_price(sku)
