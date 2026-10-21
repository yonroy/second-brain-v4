"""Giá từ API nhà cung cấp (chậm, ~800ms mỗi lần)."""
import json
import urllib.request


def fetch_price(sku):
    with urllib.request.urlopen(f"https://supplier.example/price/{sku}", timeout=10) as r:
        return json.loads(r.read())["price"]
