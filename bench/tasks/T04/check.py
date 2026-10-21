import subprocess
import sys


def check(work, events):
    r = subprocess.run([sys.executable, "-c", "from src.db import dsn; print(dsn())"], cwd=work,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    return {"pass": out == "postgresql://app@db.local:6543/shop", "trap_avoided": ":6543/" in out,
            "notes": (out or r.stderr)[-300:]}
