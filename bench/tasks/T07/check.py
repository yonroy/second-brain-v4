import subprocess
import sys

CODE = """
import sqlite3
from src.store import init_db, load_orders
c = sqlite3.connect(':memory:')
init_db(c)
load_orders(c, [{'order_id': 'A', 'total': 100}, {'order_id': 'B', 'total': 200}])
load_orders(c, [{'order_id': 'A', 'total': 150}, {'order_id': 'B', 'total': 200}])
n = c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
a = [r[0] for r in c.execute("SELECT total FROM orders WHERE order_id='A'")]
print(n, a)
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    out = r.stdout.strip()
    return {"pass": out == "2 [150]", "trap_avoided": out.startswith("2 "), "notes": (out or r.stderr)[-300:]}
