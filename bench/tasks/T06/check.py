import json
import subprocess
import sys

CASES = [(1005, 10, 905), (25, 50, 13), (100, 0, 100), (999, 33, 669), (15, 50, 8)]


def check(work, events):
    code = ("import json; from src.money import apply_discount as f; "
            "print(json.dumps([[f(a,p), type(f(a,p)).__name__] for a,p in %r]))" % [(a, p) for a, p, _ in CASES])
    r = subprocess.run([sys.executable, "-c", code], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"pass": False, "trap_avoided": False, "notes": (r.stdout + r.stderr)[-300:]}
    vals = [g[0] for g in got]
    ints = all(g[1] == "int" for g in got)
    want = [c[2] for c in CASES]
    return {"pass": vals == want and ints, "trap_avoided": ints and vals[1] == 13 and vals[4] == 8,
            "notes": json.dumps(got)}
