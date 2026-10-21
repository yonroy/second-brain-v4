import re
import subprocess
import sys


def check(work, events):
    left = [str(p.relative_to(work)) for p in work.rglob("*.py")
            if ".git" not in p.parts and re.search(r"\bget_usr\b", p.read_text(encoding="utf-8", errors="ignore"))]
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=work,
                       capture_output=True, text=True, timeout=120)
    g = subprocess.run([sys.executable, "-c", "from src.users import get_user; print(get_user(5)['name'])"], cwd=work,
                       capture_output=True, text=True, timeout=60)
    ok = r.returncode == 0 and g.stdout.strip() == "user5"
    return {"pass": ok and not left, "trap_avoided": not left, "notes": f"left={left} tests_rc={r.returncode}"}
