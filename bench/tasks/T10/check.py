import subprocess
import sys

CODE = """
from datetime import datetime, timezone
from src.delivery import format_eta
print(format_eta(datetime(2026, 3, 5, 20, 0, tzinfo=timezone.utc), 2))
print(format_eta(datetime(2026, 3, 5, 1, 30, tzinfo=timezone.utc), 1))
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    out = r.stdout.strip().splitlines()
    ok = out == ["05:00 06/03/2026", "09:30 05/03/2026"]
    return {"pass": ok, "trap_avoided": ok or (bool(out) and not out[0].startswith("22:00")), "notes": (r.stdout + r.stderr)[-300:]}
