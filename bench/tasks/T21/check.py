import json
import subprocess
import sys

CODE = r"""
import json
from src.schema import connect
from src.export import top_customers
c = connect()
cols = [r[1] for r in c.execute("PRAGMA table_info(customers)")]
print(json.dumps([cols, top_customers(c)]))  # ASCII-escaped: the child pipe is cp1252 on Windows
"""


def check(work, events):
    left = [str(p.relative_to(work)) for p in work.rglob("*") if p.is_file() and ".git" not in p.parts
            and ".claude" not in p.parts and p.suffix in (".py", ".sql", ".json")
            and "cust_name" in p.read_text(encoding="utf-8", errors="ignore")]
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60, encoding="utf-8")
    try:
        cols, top = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"pass": False, "trap_avoided": None, "notes": (r.stdout + r.stderr)[-300:]}
    ok = "customer_name" in cols and top == [{"customer_name": "Bình", "spent": 500}, {"customer_name": "An", "spent": 300}]
    return {"pass": ok and not left, "trap_avoided": None, "notes": f"left={left} top={top}"[:300]}
