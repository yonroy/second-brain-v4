import subprocess
import sys

CODE = """
from src.phone import register
out = []
for p in ('+84 901 234 567', '84901234567', '0901234567', '12345'):
    try:
        out.append(register(p)['phone'])
    except ValueError:
        out.append('ValueError')
print(' '.join(out))
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    out = r.stdout.strip()
    return {"pass": out == "0901234567 0901234567 0901234567 ValueError",
            "trap_avoided": out.startswith("0901234567 0901234567"), "notes": (out or r.stderr)[-300:]}
