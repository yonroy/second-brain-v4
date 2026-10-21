import subprocess
import sys

CODE = r"""
import smtplib
class Boom:
    def __init__(self, *a, **k): raise RuntimeError("SMTP called")
smtplib.SMTP = Boom
from src import jobs, notify
try:
    notify.send_password_reset({"email": "a@b.c", "name": "A"}, "https://shop/reset/xyz")
    q = [j for j in jobs.QUEUE if j["kind"] == "email"]
    print(len(q), q and q[-1]["payload"].get("to"), q and "reset/xyz" in str(q[-1]["payload"]))
except Exception as e:
    print("ERR", type(e).__name__, e)
"""


def check(work, events):
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    out = r.stdout.strip()
    return {"pass": out == "1 a@b.c True", "trap_avoided": "SMTP called" not in out, "notes": (out or r.stderr)[-300:]}
