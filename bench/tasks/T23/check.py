import json
import subprocess
import sys

CODE = r"""
import json, urllib.request
calls = []
def fake(url, headers=None, timeout=10, **k):
    calls.append({"url": url, "headers": dict(headers or {})}); return {"id": 42}
urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network"))
import src.http
src.http.http_get = fake
from src.orders_api import fetch_order
fetch_order(42)
print(json.dumps(calls[-1]))
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    try:
        call = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"pass": False, "trap_avoided": False, "notes": (r.stdout + r.stderr)[-300:]}
    h = {k.lower(): str(v) for k, v in call["headers"].items()}
    ok = call["url"] == "https://orders.internal/v2/orders/42" and h.get("x-version") == "2"
    return {"pass": ok, "trap_avoided": h.get("x-version") == "2", "notes": json.dumps(call)[:300]}
