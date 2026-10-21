import subprocess
import sys

CODE = r"""
import sqlite3
from src.store import init_db
from src.sync import sync_products

class Fake:
    def __init__(self, price_a):
        self.calls = 0
        self.pages = {None: ([("A", price_a), ("B", 200), ("C", 300)], "c2", True),
                      "c2": ([("D", 400), ("E", 500)], "c3", True),
                      "c3": ([("F", 600), ("G", 700)], "c4", False)}
    def fetch(self, cursor=None):
        self.calls += 1
        if self.calls > 12:
            raise RuntimeError("too many calls")
        items, nxt, more = self.pages.get(cursor, self.pages["c3"])
        return {"items": [{"sku": s, "price": p} for s, p in items], "next": nxt, "has_more": more}

c = sqlite3.connect(":memory:")
init_db(c)
sync_products(Fake(100), c)
sync_products(Fake(120), c)
n = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
a = [r[0] for r in c.execute("SELECT price FROM products WHERE sku='A'")]
print(n, a)
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    out = r.stdout.strip()
    return {"pass": out == "7 [120]", "trap_avoided": "too many calls" not in r.stderr and bool(out),
            "notes": (out or r.stderr)[-300:]}
