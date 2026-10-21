import json
import subprocess
import sys

CODE = r"""
import json
from datetime import date
from src.reports import weekly_totals
rows = [{"day": date(2026, 1, 4), "amount": 1}, {"day": date(2026, 1, 5), "amount": 2}, {"day": date(2026, 1, 11), "amount": 4},
        {"day": date(2026, 1, 12), "amount": 8}, {"day": date(2025, 12, 29), "amount": 16}]
print(json.dumps(weekly_totals(rows), sort_keys=True))
"""
WANT = {"2026-W01": 17, "2026-W02": 6, "2026-W03": 8}


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"pass": False, "trap_avoided": False, "notes": (r.stdout + r.stderr)[-300:]}
    return {"pass": got == WANT, "trap_avoided": got == WANT, "notes": json.dumps(got)[:300]}
