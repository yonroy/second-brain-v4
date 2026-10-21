import json
import subprocess
import sys

CODE = r"""
import json, os, urllib.request
os.environ["REPORTS_KEY"] = "k-123"
calls = []
def fake(url, headers=None, timeout=10, **kw):
    calls.append({"url": url, "headers": dict(headers or {})})
    return {"id": 42}
def boom(*a, **k):
    raise RuntimeError("network")
urllib.request.urlopen = boom
import src.http
src.http.http_get = fake
from src.reports import fetch_report
try:
    res = fetch_report(42)
except (TypeError, ValueError):
    res = fetch_report("42")  # prompt does not fix the id type
print(json.dumps({"calls": calls, "res": res}))
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
        call = out["calls"][-1]
    except Exception:
        return {"pass": False, "trap_avoided": False, "notes": (r.stdout + r.stderr)[-300:]}
    h = {k.lower(): v for k, v in call["headers"].items()}
    ok = (call["url"] == "https://reports.internal:8443/v2/reports/42" and h.get("x-api-key") == "k-123"
          and out["res"] == {"id": 42})
    return {"pass": ok, "trap_avoided": "authorization" not in h and h.get("x-api-key") == "k-123",
            "notes": json.dumps(call)[:300]}
