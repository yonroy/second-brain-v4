"""Client API sản phẩm của nhà cung cấp.

fetch(cursor=None) -> {"items": [{"sku": str, "price": int}, ...], "next": cursor của trang sau}
"""
import json
import urllib.request


class ProductsAPI:
    def __init__(self, base="https://supplier.example/api"):
        self.base = base

    def fetch(self, cursor=None):
        url = f"{self.base}/products" + (f"?cursor={cursor}" if cursor else "")
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
