import subprocess
import sys

CODE = """
from src.registry import dispatch, run_schedules
print(dispatch('order.paid', {'id': 1}))
print(run_schedules())
"""


def check(work, events):
    left = [str(p.relative_to(work)) for p in work.rglob("*") if p.is_file() and ".git" not in p.parts
            and ".claude" not in p.parts and p.suffix in (".py", ".toml", ".json")
            and "handle_order_paid" in p.read_text(encoding="utf-8", errors="ignore")]
    r = subprocess.run([sys.executable, "-c", CODE], cwd=work, capture_output=True, text=True, timeout=60)
    ok = r.stdout.strip().splitlines() == ["paid:1", "['paid:batch']"]
    g = subprocess.run([sys.executable, "-c", "from src.handlers import on_order_paid"], cwd=work, capture_output=True)
    return {"pass": ok and not left and g.returncode == 0, "trap_avoided": "schedules.json" not in " ".join(left) and ok,
            "notes": f"left={left} out={(r.stdout + r.stderr)[-160:]}"}
