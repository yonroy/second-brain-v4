import time

from src import supplier

TTL = 15
_cache = {}


def get_price(sku):
    now = time.monotonic()
    hit = _cache.get(sku)
    if hit and now - hit[1] < TTL:
        return hit[0]
    price = supplier.fetch_price(sku)
    _cache[sku] = (price, now)
    return price
