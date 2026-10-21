import subprocess
import sys

CODE = r"""
import inspect
from src import tax
from src.cart import total
from src.invoice import make
from src.reports.monthly import rate_table
from src.api.handlers import handle
from scripts.backfill import run
sig = list(inspect.signature(tax.tax_rate).parameters)
req = all(p.default is inspect.Parameter.empty for p in inspect.signature(tax.tax_rate).parameters.values())
print(sig[:2] == ["category", "region"] and req, round(tax.tax_rate("food", "US"), 4),
      total([{"price": 100, "cat": "food"}]), make({"price": 200, "cat": "electronics"})["tax"],
      round(rate_table(["food"])["food"], 4), round(handle({})["rate"], 4), [round(x, 4) for x in run()])
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    out = r.stdout.strip()
    want = "True 0.08 105 20 0.05 0.05 [0.0]"
    return {"pass": out == want, "trap_avoided": None, "notes": (out or r.stderr)[-300:]}
