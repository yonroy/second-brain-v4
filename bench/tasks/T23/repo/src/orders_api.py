from src import http

BASE = "https://orders.internal"


def fetch_order(order_id):
    return http.http_get(f"{BASE}/v1/orders/{order_id}")
