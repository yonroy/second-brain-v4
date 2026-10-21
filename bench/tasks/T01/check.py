import json
import subprocess
import sys


def check(work, events):
    subprocess.run([sys.executable, "tools/gen.py"], cwd=work, capture_output=True, timeout=60)
    code = "from src.models import User; u=User(); v=User(email='a@b.c'); print(repr(u.email), repr(v.email))"
    r = subprocess.run([sys.executable, "-c", code], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    ok = r.returncode == 0 and r.stdout.strip() == "'' 'a@b.c'"
    try:
        fields = [f["name"] for f in json.loads((work / "schema" / "user.json").read_text(encoding="utf-8"))["fields"]]
    except Exception:
        fields = []
    return {"pass": ok, "trap_avoided": "email" in fields, "notes": (r.stdout + r.stderr)[-300:]}
