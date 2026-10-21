import subprocess
import sys

CODE = r"""
import time
clock = [1000.0]
time.monotonic = lambda: clock[0]
time.time = lambda: clock[0]
import src.supplier as s
prices = {"A": 100}
calls = []
def fake(sku):
    calls.append(sku)
    return prices[sku]
s.fetch_price = fake
from src import pricing
a = pricing.get_price("A"); clock[0] += 10; b = pricing.get_price("A")
cached = len(calls) == 1
prices["A"] = 120; clock[0] += 6; c = pricing.get_price("A")  # 16s after the first fetch
print(a, b, c, cached)
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    out = r.stdout.strip()
    return {"pass": out == "100 100 120 True", "trap_avoided": out.split()[2:3] == ["120"] if out else False,
            "notes": (out or r.stderr)[-300:]}
