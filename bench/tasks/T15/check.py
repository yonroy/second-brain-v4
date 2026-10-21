import json
import subprocess
import sys

CODE = r"""
import json
from src.wallet import transfer
out = []
def run(w, *a):
    try:
        r = transfer(w, *a)
        out.append([{"ok": r.get("ok"), "error": r.get("error")}, w])
    except Exception as e:
        out.append([{"raised": type(e).__name__}, w])
run({"a": 50, "b": 0}, "a", "b", 80)
run({"a": 50, "b": 0}, "a", "b", 0)
run({"a": 50, "b": 0}, "a", "a", 10)
run({"a": 50, "b": 0}, "a", "zz", 10)
run({"a": 50, "b": 0}, "a", "b", 30)
print(json.dumps(out))
"""
WANT = [[{"ok": False, "error": "INSUFFICIENT_FUNDS"}, {"a": 50, "b": 0}],
        [{"ok": False, "error": "INVALID_AMOUNT"}, {"a": 50, "b": 0}],
        [{"ok": False, "error": "SAME_WALLET"}, {"a": 50, "b": 0}],
        [{"ok": False, "error": "UNKNOWN_WALLET"}, {"a": 50, "b": 0}],
        [{"ok": True, "error": None}, {"a": 20, "b": 30}]]


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"pass": False, "trap_avoided": False, "notes": (r.stdout + r.stderr)[-300:]}
    raised = any("raised" in g[0] for g in got)
    return {"pass": got == WANT, "trap_avoided": not raised, "notes": json.dumps(got)[:300]}
