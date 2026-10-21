"""Hàng đợi job (worker chạy riêng)."""
QUEUE = []


def enqueue(kind, payload):
    QUEUE.append({"kind": kind, "payload": payload})
